#!/usr/bin/env python3
import sys
import copy
import rospy
import math
import numpy as np
import time
import open3d as o3d
import cv2
import actionlib

import geometry_msgs.msg
from geometry_msgs.msg import Pose, PoseStamped, PoseArray
import std_msgs.msg
from std_msgs.msg import Int8, MultiArrayDimension, MultiArrayLayout, Int32MultiArray, Float32MultiArray, Bool, Header
from sensor_msgs.msg import PointCloud2, PointField, JointState
import sensor_msgs.point_cloud2 as pc2
from iiwa_msgs.msg import JointPosition, Spline, SplineSegment, MoveAlongSplineAction, MoveToJointPositionAction, MoveToJointPositionGoal, MoveAlongSplineGoal
from iiwa_msgs.srv import SetPTPJointSpeedLimits, SetEndpointFrame, SetPTPCartesianSpeedLimits

import rob9Utils.transformations as transform
from rob9Utils.graspGroup import GraspGroup
from rob9Utils.grasp import Grasp
import rob9Utils.moveit as moveit
from cameraService.cameraClient import CameraClient
from affordanceService.client import AffordanceClient
from grasp_service.client import GraspingGeneratorClient
from rob9Utils.visualize import visualizeGrasps6DOF

from moveit_scripts.srv import *
from moveit_scripts.msg import *
from grasp_aff_association.srv import *
from rob9.srv import graspGroupSrv, graspGroupSrvResponse

from moveit_msgs.srv import *
from moveit_msgs.msg import PositionIKRequest, RobotState, MoveItErrorCodes

import time

def setEndpointFrame(frame_id = "iiwa_link_ee"):
	print("Setting endpoint frame to \"", frame_id, "\"...")
	set_endpoint_frame_client = rospy.ServiceProxy("/iiwa/configuration/setEndpointFrame", SetEndpointFrame)
	response = set_endpoint_frame_client.call(frame_id)

	if not response.success:
		print("Service call returned error: ", response.error)
		return False

	return True

def setPTPJointSpeedLimits():
    print("Setting PTP joint speed limits...")
    set_ptp_joint_speed_client = rospy.ServiceProxy("/iiwa/configuration/setPTPJointLimits", SetPTPJointSpeedLimits)

    joint_relative_vel = 0.2
    joint_relative_acc = 0.5
    response = set_ptp_joint_speed_client.call(joint_relative_vel, joint_relative_acc)


    if not response.success:
        print("Service call returned error: ", response.error)
        return False


    return True

def setPTPCartesianSpeedLimits():
    print("Setting PTP Cartesian speed limits...")
    set_ptp_cartesian_speed_client = rospy.ServiceProxy("/iiwa/configuration/setPTPCartesianLimits", SetPTPCartesianSpeedLimits)

    max_cartesian_vel = 0.5
    max_cartesian_acc = 0.5
    max_cartesian_jerk = -1.0 # ignore
    max_orientation_vel = 0.5
    max_orientation_acc = 0.5
    max_orientation_jerk = -1.0 # ignore

    response = set_ptp_cartesian_speed_client(max_cartesian_vel, max_cartesian_acc, max_cartesian_jerk,
                                                max_orientation_vel, max_orientation_acc, max_orientation_jerk)

    if not response.success:
        print("Service call returned error: ", response.error);
        return False

    return True

def getSplineSegment (x, y, z, qx, qy, qz, qw, type = 0):
    segment = SplineSegment()

    segment.type = type;

    segment.point.poseStamped.header.frame_id = "iiwa_link_0"

    segment.point.poseStamped.pose.position.x = x
    segment.point.poseStamped.pose.position.y = y
    segment.point.poseStamped.pose.position.z = z

    segment.point.poseStamped.pose.orientation.x = qx
    segment.point.poseStamped.pose.orientation.y = qy
    segment.point.poseStamped.pose.orientation.z = qz
    segment.point.poseStamped.pose.orientation.w = qw

    segment.point.redundancy.status = -1
    segment.point.redundancy.turn = -1

    return segment


def associateGraspAffordance(graspData, objects, masks, cloud, cloud_uv, demo = False):

    graspMsg = graspData.toGraspGroupMsg()

    objectMsg = Int32MultiArray()
    objectMsg.data = objects.tolist()

    intToLabel = {0: 'class', 1: 'height', 2: 'width'}
    maskMsg = Int32MultiArray()

    masks = np.reshape(masks, (-1, masks.shape[2], masks.shape[3]))

    # constructing mask message
    for i in range(3):
        dimMsg = MultiArrayDimension()
        dimMsg.label = intToLabel[i]
        stride = 1
        for j in range(3-i):
            stride = stride * masks.shape[i+j]
        dimMsg.stride = stride
        dimMsg.size = masks.shape[i]
        maskMsg.layout.dim.append(dimMsg)
    maskMsg.data = masks.flatten().astype(int).tolist()

    demoMsg = Bool()
    demoMsg.data = demo

    uvDim1 = MultiArrayDimension()
    uvDim1.label = "length"
    uvDim1.size = int(cloud_uv.shape[0] * cloud_uv.shape[1])
    uvDim1.stride = cloud_uv.shape[0]

    uvDim2 = MultiArrayDimension()
    uvDim2.label = "pair"
    uvDim2.size = cloud_uv.shape[1]
    uvDim2.stride = cloud_uv.shape[1]

    uvLayout = MultiArrayLayout()
    uvLayout.dim.append(uvDim1)
    uvLayout.dim.append(uvDim2)

    uvMsg = Float32MultiArray()
    uvMsg.data = cloud_uv.flatten().tolist()
    uvMsg.layout = uvLayout

    FIELDS_XYZ = [
        PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
    ]

    header = Header()
    header.stamp = rospy.Time.now()
    header.frame_id = "ptu_camera_color_optical_frame"
    cloudMsg = pc2.create_cloud(header, FIELDS_XYZ, cloud)

    rospy.wait_for_service('grasp_affordance_association/associate')
    get_grasps_service = rospy.ServiceProxy('grasp_affordance_association/associate', graspGroupSrv)
    response = get_grasps_service(demoMsg, graspMsg, objectMsg, maskMsg, cloudMsg, uvMsg)

    return GraspGroup().fromGraspGroupSrv(response)

def send_trajectory_to_rviz(plan):
    print("Trajectory was sent to RViZ")
    display_trajectory = moveit_msgs.msg.DisplayTrajectory()
    #display_trajectory.trajectory_start = robot.get_current_state()
    display_trajectory.trajectory_start = moveit.getCurrentState()
    display_trajectory.trajectory.append(plan)
    display_trajectory_publisher.publish(display_trajectory)

def execute_spline_trajectory(plan):
    print("Executing trajectory with spline motion")

    # Compute cartesian poses for each point in joint trajectory

    rospy.wait_for_service('/iiwa/compute_fk')
    moveit_fk = rospy.ServiceProxy('/iiwa/compute_fk', GetPositionFK)

    cartesian_poses = []

    end_effector_link = ['iiwa_link_ee']
    joint_names = []
    joint_positions = []
    for joint_position in plan.joint_trajectory.points:
        for i in range(7):
          joint_names.append('iiwa_joint_'+str(i + 1)) # joint names, see /iiwa/joint_state
          print(joint_position)
          joint_positions.append(joint_position.positions[i])
        header = Header(0,rospy.Time.now(),"iiwa_link_0") # base of IIWA
        rs = RobotState()
        rs.joint_state.name = joint_names
        rs.joint_state.position = joint_positions
        fk_result = moveit_fk(header, end_effector_link, rs) # Lookup the pose

        x, y, z = fk_result.pose_stamped[0].pose.position.x, fk_result.pose_stamped[0].pose.position.y, fk_result.pose_stamped[0].pose.position.z
        qx, qy, qz, qw = fk_result.pose_stamped[0].pose.orientation.x, fk_result.pose_stamped[0].pose.orientation.y, fk_result.pose_stamped[0].pose.orientation.z, fk_result.pose_stamped[0].pose.orientation.w

        cartesian_poses.append([x, y, z, qx, qy, qz, qw])

    # Assemble spline with SPL motions

    spline_motion = MoveAlongSplineGoal()

    for pose in cartesian_poses:
        x, y, z, qx, qy, qz, qw = pose
        spline_motion.spline.segments.append(getSplineSegment(x, y, z, qx, qy, qz, qw, type = 0))

    # Send and execute
    spline_motion_client = actionlib.SimpleActionClient("/iiwa/action/move_along_spline", MoveAlongSplineAction)

    print("Waiting for action servers to start...")
    spline_motion_client.wait_for_server()

    spline_motion_client.send_goal(spline_motion)
    spline_motion_client.wait_for_result()


def callbackJointState(msg):
    global robot_is_moving

    positive_velocity = False
    for vel in msg.velocity:
        if round(vel, 1) != 0:
            positive_velocity = True

    if positive_velocity:
        robot_is_moving = True
    else:
        robot_is_moving = False


def callback(msg):
    global resp_trajectories, grasps_affordance, robot_is_moving
    id = msg.data[0]
    requested_affordance_id = msg.data[1]

    affordance_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9]

    # Select affordance label to grasp
    graspObj = GraspGroup(grasps = copy.deepcopy(grasps_affordance.getgraspsByTool(id = id)))
    graspAffordance = GraspGroup(grasps = [])

    for affordance_id in affordance_ids:
        if affordance_id == requested_affordance_id:# or affordance_id != 7:
            graspAffordance.combine(GraspGroup(grasps = copy.deepcopy(graspObj.getgraspsByAffordanceLabel(label = affordance_id) ) ))

    grasps_affordance_tool = graspAffordance

    grasp_waypoints_path = computeWaypoints(grasps_affordance_tool, offset = 0.1)


    azimuthAngleLimit = [-1*math.pi, 1*math.pi]
    polarAngleLimit = [0, 0.5*math.pi]
    #grasp_waypoints_path = filterBySphericalCoordinates(grasp_waypoints_path, azimuth = azimuthAngleLimit, polar = polarAngleLimit)

    print("Calling the trajectory service")
    rospy.wait_for_service('iiwa/get_trajectories')
    get_trajectories = rospy.ServiceProxy('iiwa/get_trajectories', GetTrajectories)
    resp_trajectories = get_trajectories(grasp_waypoints_path)
    print("I have received a trajectory server response ")

    id_list_duplicates = []
    for i in range(len(resp_trajectories.trajectories.trajectories)):
        id_list_duplicates.append(resp_trajectories.trajectories.trajectories[i].joint_trajectory.header.frame_id)
    id_list = list(dict.fromkeys(id_list_duplicates))
    print("id_list " + str(id_list))

    id = str(id)
    plans = []
    goal_poses = []
    for i in range(len(resp_trajectories.trajectories.trajectories)):
        if resp_trajectories.trajectories.trajectories[i].joint_trajectory.header.frame_id == id:
            plans.append(resp_trajectories.trajectories.trajectories[i])

    for i in range(len(resp_trajectories.trajectories_poses.poses)):
        if resp_trajectories.trajectories_poses.poses[i].header.frame_id == id:
            goal_poses.append(resp_trajectories.trajectories_poses.poses[i])

    waypoint_msg = geometry_msgs.msg.PoseStamped()
    waypoint_msg.header.frame_id = "world"
    waypoint_msg.header.stamp = rospy.Time.now()
    waypoint_msg.pose = goal_poses[0].pose
    pub_waypoint.publish(waypoint_msg)

    goal_msg = geometry_msgs.msg.PoseStamped()
    goal_msg.header.frame_id = "world"
    goal_msg.header.stamp = rospy.Time.now()
    goal_msg.pose = goal_poses[1].pose
    pub_grasp.publish(goal_msg)

    for i in range(3):
        send_trajectory_to_rviz(plans[i])
        #print(type(plans[i]))
        #pub_joint_command(plans[i]) # outcommented by Albert Wed 23 March 09:06
        #moveit.execute(plans[i]) # incommented by Albert Wed 23 March 09:06
        execute_spline_trajectory(plans[i])
        while robot_is_moving == True:
            print("robot_is_moving: ", robot_is_moving)
            rospy.sleep(0.1)
        if i == 1:
            gripper_pub.publish(close_gripper_msg) # incommented by Albert Wed 23 March 09:06
            rospy.sleep(1) # incommented by Albert Wed 23 March 09:06
            print("I have grasped!")
        input("Press Enter when you are ready to move the robot back to the ready pose") # outcommented by Albert Wed 23 March 09:06
    while robot_is_moving == True:
        rospy.sleep(0.1)
    moveit.moveToNamed("ready")
    while robot_is_moving == True:
        rospy.sleep(0.1)
    moveit.moveToNamed("handover")
    while robot_is_moving == True:
        rospy.sleep(0.1)
    #input("Press Enter when you are ready to move the robot back to the ready pose")

    #moveit.moveToNamed("ready")
    gripper_pub.publish(open_gripper_msg)

def computeWaypoints(graspObjects, offset = 0.1):
    """ input:  graspsObjects   -   GraspGroup() of grasps
                offset          -   float, in meters for waypoint in relation to grasp
        output:                 -   nav_msgs Path
    """

    world_frame = "world"
    ee_frame = "right_ee_link"
    print("Computing waypoints for ", len(graspObjects), " task-oriented grasps.")

    grasps, waypoints = [], []
    for i in range(len(graspObjects)):

        grasp = graspObjects[i]

        graspCamera = copy.deepcopy(grasp)
        waypointCamera = copy.deepcopy(grasp)

        # computing waypoint in camera frame
        rotMat = graspCamera.getRotationMatrix()
        offsetArr = np.array([[offset], [0.0], [0.0]])
        offsetCam = np.transpose(np.matmul(rotMat, offsetArr))[0]

        waypointCamera.position.x += -offsetCam[0]
        waypointCamera.position.y += -offsetCam[1]
        waypointCamera.position.z += -offsetCam[2]

        waypointWorld = Grasp().fromPoseStampedMsg(transform.transformToFrame(waypointCamera.toPoseStampedMsg(), world_frame))
        graspWorld = Grasp().fromPoseStampedMsg(transform.transformToFrame(graspCamera.toPoseStampedMsg(), world_frame))

        waypointWorld.frame_id = str(graspObjects[i].tool_id) # we should probably do away with storing it in the header
        graspWorld.frame_id = str(graspObjects[i].tool_id)
        waypoints.append(waypointWorld.toPoseStampedMsg())
        grasps.append(graspWorld.toPoseStampedMsg())
        print(i+1, " / ", len(graspObjects))

    grasps_msg = nav_msgs.msg.Path()
    grasps_msg.header.frame_id = "world"
    grasps_msg.header.stamp = rospy.Time.now()
    for i in range(len(grasps)):
        grasps_msg.poses.append(waypoints[i])
        grasps_msg.poses.append(grasps[i])

    return grasps_msg

def filterBySphericalCoordinates(poses, azimuth, polar):
    """ input:  poses   -   nav_msgs/Path, a list of waypoints and poses in pairs
                azimut  -   numpy array shape 2, [minAngle, maxAngle]
                polar   -   numpy array shape 2, [minAngle, maxAngle]
        output:         -   nav_msgs/Path a list of waypoints and poses in pairs
        Only returns waypoints and grasps that are inside the spherical angle
        limits
    """
    grasps, waypoints = [], []
    for i in range(int(len(poses.poses) / 2)):

        waypointWorld = poses.poses[i]
        graspWorld = poses.poses[i + 1]

        # computing local cartesian coordinates
        x = waypointWorld.pose.position.x - graspWorld.pose.position.x
        y = waypointWorld.pose.position.y - graspWorld.pose.position.y
        z = waypointWorld.pose.position.z - graspWorld.pose.position.z

        # computing spherical coordinates
        r, polarAngle, azimuthAngle = transform.cartesianToSpherical(x, y, z)

        azimuthAngleLimit = azimuth
        polarAngleLimit = polar

        # Evaluating angle limits
        if azimuthAngle > azimuthAngleLimit[0] and azimuthAngle < azimuthAngleLimit[1]:
            if polarAngle > polarAngleLimit[0] and polarAngle < polarAngleLimit[1]:
                waypoints.append(waypointWorld)
                grasps.append(graspWorld)


    if len(grasps) == 0 or len(waypoints) == 0:
        print("Could not find grasp with appropriate angle")
        grasp_msg = nav_msgs.msg.Path()
        return grasps_msg # in case no grasps can be found, return empty message

    grasps_msg = nav_msgs.msg.Path()
    grasps_msg.header.frame_id = "world"
    grasps_msg.header.stamp = rospy.Time.now()
    for i in range(len(grasps)):
        grasps_msg.poses.append(waypoints[i])
        grasps_msg.poses.append(grasps[i])

    return grasps_msg

def sortByOrientationDifference(poses):
    # Should be moved to GraspGroup.py
    # not yet implemented! this is the old deltaRPY
    """ input:  poses   -   nav_msgs/Path, a list of waypoints and grasps in pairs
        output:         -   nav_msgs/Path, a list of waypoints and grasps in pairs
        Sorted by the relative angle difference compared to current robot pose
    """

    eeWorld = tf_buffer.lookup_transform("world", "right_ee_link", rospy.Time.now(), rospy.Duration(1.0))
    weightedSums = []

    for i in range(len(grasps)):
        deltaRPY = abs(transform.delta_orientation(grasps[i], eeWorld))
        weightedSum = 0.2*deltaRPY[0]+0.4*deltaRPY[1]+0.4*deltaRPY[2]
        weightedSums.append(weightedSum)

    weightedSums_sorted = sorted(weightedSums)
    grasps_sorted = [None]*len(grasps) # sorted according to delta orientation from current orientation of gripper
    waypoints_sorted = [None]*len(waypoints)

    for i in range(len(weightedSums)):
        num = weightedSums_sorted[i]
        index = weightedSums.index(num)
        grasps_sorted[i] = grasps[index]
        waypoints_sorted[i] = waypoints[index]

if __name__ == '__main__':
    global grasps_affordance, img, affClient, pcd
    demo = std_msgs.msg.Bool()
    demo.data = False
    if len(sys.argv) > 1:
        if sys.argv[1] == 'demo':
            demo.data = True
            print("Demo = True")
        else:
            print("Invalid input argument")
            exit()

    print("Init")
    rospy.init_node('moveit_subscriber', anonymous=True)

    set_ee = True
    if not setEndpointFrame():
        set_ee = False
    print("STATUS end point frame was changed: ", set_ee)

    set_PTP_speed_limit = True
    if not setPTPJointSpeedLimits():
        set_PTP_speed_limit = False
    print("STATUS PTP joint speed limits was changed: ", set_PTP_speed_limit)

    set_PTP_cart_speed_limit = True
    if not setPTPCartesianSpeedLimits():
        set_PTP_cart_speed_limit = False
    print("STATUS PTP cartesian speed limits was changed: ", set_PTP_cart_speed_limit)

    #rospy.Subscriber('tool_id', Int8, callback)
    rospy.Subscriber('objects_affordances_id', Int32MultiArray, callback )
    rospy.Subscriber('/iiwa/joint_states', JointState, callbackJointState)
    gripper_pub = rospy.Publisher('iiwa/gripper_controller', Int8, queue_size=10, latch=True)
    pub_grasp = rospy.Publisher('iiwa/pose_to_reach', PoseStamped, queue_size=10)
    pub_waypoint = rospy.Publisher('iiwa/pose_to_reach_waypoint', PoseStamped, queue_size=10)
    pub_iiwa = rospy.Publisher('iiwa/command/JointPosition', JointPosition, queue_size=10 )
    display_trajectory_publisher = rospy.Publisher('iiwa/move_group/display_planned_path',
                                                   moveit_msgs.msg.DisplayTrajectory,
                                                   queue_size=20)
    # DO NOT REMOVE THIS SLEEP, it allows gripper_pub to establish connection to the topic
    rospy.sleep(0.1)
    rospy.sleep(2)

    vid_capture = cv2.VideoCapture(0)

    reset_gripper_msg = std_msgs.msg.Int8()
    reset_gripper_msg.data = 0
    activate_gripper_msg = std_msgs.msg.Int8()
    activate_gripper_msg.data = 1
    close_gripper_msg = std_msgs.msg.Int8()
    close_gripper_msg = 2
    open_gripper_msg = std_msgs.msg.Int8()
    open_gripper_msg.data = 3
    basic_gripper_msg = std_msgs.msg.Int8()
    basic_gripper_msg.data = 4
    pinch_gripper_msg = std_msgs.msg.Int8()
    pinch_gripper_msg.data = 5

    gripper_pub.publish(reset_gripper_msg)
    gripper_pub.publish(activate_gripper_msg)
    gripper_pub.publish(open_gripper_msg)
    gripper_pub.publish(pinch_gripper_msg)
    moveit.moveToNamed("ready")

    print("Services init")

    print("Camera is capturing new scene")

    cam = CameraClient()
    cam.captureNewScene()
    cloud, cloudColor = cam.getPointCloudStatic()
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(cloud)
    pcd.colors = o3d.utility.Vector3dVector(cloudColor)

    cloud_uv = cam.getUvStatic()
    img = cam.getRGB()

    width = 1280
    height = 960
    h_divisions = 4
    w_divisions = 2
    viz_h_unit = int(height / h_divisions)
    viz_w_unit = viz_h_unit

    print("Generating grasps")

    # Get grasps from grasp generator
    graspClient = GraspingGeneratorClient()

    collision_thresh = 0.01 # Collision threshold in collision detection
    num_view = 300 # View number
    score_thresh = 0.0 # Remove every grasp with scores less than threshold
    voxel_size = 0.2

    graspClient.setSettings(collision_thresh, num_view, score_thresh, voxel_size)

    # Load the network with GPU (True or False) or CPU
    graspClient.start(GPU=True)

    graspData = graspClient.getGrasps()

    print("Got ", len(graspData), " grasps")

    all_grasp_viz_internal = visualizeGrasps6DOF(pcd, graspData)
    o3d.visualization.draw_geometries([pcd, *all_grasp_viz_internal])

    print("Segmenting affordance maps")
    # Run affordance analyzer
    affClient = AffordanceClient()

    affClient.start(GPU=False)
    _ = affClient.run(img, CONF_THRESHOLD = 0.5)

    masks, labels, scores, bboxs = affClient.getAffordanceResult()

    masks = affClient.processMasks(masks, conf_threshold = 0, erode_kernel=(1,1))

    # Visualize object detection and affordance segmentation to confirm
    cv2.imwrite("rgb.png", img)
    cv2.imshow("Detections", affClient.visualizeBBox(img, labels, bboxs, scores))
    cv2.imwrite("detections.png", affClient.visualizeBBox(img, labels, bboxs, scores))
    cv2.waitKey(0)
    cv2.imshow("mask", affClient.visualizeMasks(img, masks))
    cv2.waitKey(0)

    print("Computing task oriented grasps")

    # Associate affordances with grasps
    grasps_affordance = associateGraspAffordance(graspData, labels, masks, cloud, cloud_uv, demo = demo.data)

    print("Found ", len(grasps_affordance), " task oriented grasps")

    task_grasp_viz_internal = visualizeGrasps6DOF(pcd, grasps_affordance)
    o3d.visualization.draw_geometries([pcd, *task_grasp_viz_internal])

    grasps_affordance.sortByScore()
    grasps_affordance.thresholdByScore(0.0)

    print("Ready for command")


    try:
        rospy.spin()
    except rospy.ROSInterruptException:
        pass