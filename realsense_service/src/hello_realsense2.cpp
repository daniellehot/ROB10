#include <librealsense2/rs.hpp>
#include <librealsense2/hpp/rs_internal.hpp>

#include <iostream>
#include <sstream>
#include <unistd.h>

#include "ros/ros.h"
#include "ros/console.h"
#include "std_msgs/String.h"
#include "std_msgs/Header.h"
#include "std_msgs/Float32MultiArray.h"
#include "std_msgs/MultiArrayLayout.h"
#include "std_msgs/MultiArrayDimension.h"
#include "sensor_msgs/Image.h"
#include "sensor_msgs/PointCloud2.h"
//import sensor_msgs.point_cloud2 as pc2
#include "sensor_msgs/PointField.h"

#include <image_transport/image_transport.h>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/highgui/highgui.hpp>

#include "realsense_service/capture.h"
#include "realsense_service/depth.h"
#include "realsense_service/intrinsics.h"
// intrinsics.srv is not used
#include "realsense_service/pointcloud.h"
#include "realsense_service/rgb.h"
#include "realsense_service/uvSrv.h"

class RealsenseServer{
  public:
    int cam_width;
    int cam_height;
    int tempFilterSize;
    std::string baseService;
    //int frame_no;
    bool capture;
    bool startup;

    //captured information variables initialized to 0 or empty
    /*rs2::video_frame color_frame;
    int scolor_image;
    rs2::depth_frame depth_frame;
    int depth_image;
    int cloudGeometry;
    int cloudColor;
    int cloudGeometryStatic;
    int cloudColorStatic;
    int colorImageStatic;
    int depthImageStatic;
    int uv;
    int uvStatic;*/

    // TODO
    //int framesRGB = [];
    //int framesDepth = [];

    //self.br = CvBridge()
    //cv_bridge::CvImagePtr br;

    // TODO
    /*self.FIELDS_XYZ = [
        PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
    ]*/

    //Initialize ROS variables and functions
    ros::NodeHandle n;
    ros::ServiceServer serviceCapture;
    ros::ServiceServer serviceCaptureDepth;
    ros::ServiceServer serviceCaptureRGB;
    ros::ServiceServer serviceUVStatic;
    ros::ServiceServer servicePointCloudStatic;

    ros::Publisher pubPointCloudGeometryStatic;
    ros::Publisher pubStaticRGB;
    ros::Publisher pubStaticDepth;
    ros::Publisher pubPointCloudGeometryStaticRGB;

    bool updateStatic(realsense_service::capture::Request& req, realsense_service::capture::Response& res){
      if (req.capture.data){
        update();
        res.success.data = true;
      } else {
        std::cout<<"Client contacted the server but did not asked to capture new statics"<<std::endl;
        res.success.data = false;
      }
      return true;
    }

    bool serviceSendDepthImageStatic(realsense_service::depth::Request& req, realsense_service::depth::Response& res){
      //auto frame_depth = aligned_frames.get_depth_frame();
      //std::cout<<"width " << frame_depth.get_width() << std::endl;
      //std::cout<<"height " << frame_depth.get_height() << std::endl;
      // NOT SURE IF CV_16UC1 OR CV_8UC1, MORE OPTIONS https://stackoverflow.com/questions/13428689/whats-the-difference-between-cvtype-values-in-opencv
      rs2::depth_frame frame_depth(processed_frame);
      cv::Mat image(cv::Size(frame_depth.get_width(), frame_depth.get_height()), CV_8UC1, (void*)frame_depth.get_data(), cv::Mat::AUTO_STEP);
      //cv::Mat image(cv::Size(frame_depth.get_width(), frame_depth.get_height()), CV_32F, (void*)frame_depth.get_data(), cv::Mat::AUTO_STEP);
      cv::imwrite("my_img.png", image);
      sensor_msgs::ImagePtr img_msg = cv_bridge::CvImage(std_msgs::Header(), "mono8", image).toImageMsg();
      res.img = *img_msg;
      return true;
    }

    bool serviceSendRGBImageStatic(realsense_service::rgb::Request& req, realsense_service::rgb::Response& res){
      //auto frame_color = aligned_frames.get_color_frame();
      rs2::video_frame frame_color(processed_frame);
      cv::Mat image(cv::Size(frame_color.get_width(), frame_color.get_height()), CV_8UC3, (void*)frame_color.get_data(), cv::Mat::AUTO_STEP);
      //cv::imwrite("my_img.png", image);
      sensor_msgs::ImagePtr img_msg = cv_bridge::CvImage(std_msgs::Header(), "bgr8", image).toImageMsg();
      res.img = *img_msg;
      return true;
    }

    bool serviceGetUVStatic(realsense_service::uvSrv::Request& req, realsense_service::uvSrv::Response& res){
      std::cout <<"TODO" << std::endl;
      return true;
    }

    bool serviceGetPointCloud(realsense_service::pointcloud::Request& req, realsense_service::pointcloud::Response& res){
      std::cout <<"TODO" << std::endl;
      return true;
    }

    //Initialize realsense variables and function
    rs2::config cfg;
    rs2::pipeline pipe;
    /*REMOVE WHEN DONE*/ rs2::frameset frames;
    /*REMOVE WHEN DONE*/ rs2::frameset aligned_frames;
    rs2::pointcloud pc;
    /*REMOVE WHEN DONE*/ rs2::points points;
    const rs2::texture_coordinate* uv;
    rs2::frame processed_frame;

    RealsenseServer();
    void initializeRealsense();
    void update();
    void generatePointcloud();
};

//CONSTRUCTOR, CHANGE VALUES HERE
RealsenseServer::RealsenseServer() {
    cam_width = 1280;
    cam_height = 720;
    //tempFilterSize = 10;
    baseService = "/sensors/realsense";
    /*color_frame = 0;
    scolor_image = 0;
    depth_frame = 0;
    depth_image = 0;
    cloudGeometry = 0;
    cloudColor = 0;
    cloudGeometryStatic = 0;
    cloudColorStatic = 0;
    colorImageStatic = 0;
    depthImageStatic = 0;
    uv = 0;
    uvStatic = 0;*/

    // TODO
    //framesRGB = [];
    //framesDepth = [];

    // TOD
    /*self.FIELDS_XYZ = [
        PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
    ]*/

    //Initialize ROS
    serviceCapture = n.advertiseService(baseService + "/capture", &RealsenseServer::updateStatic, this);
    serviceCaptureDepth = n.advertiseService(baseService + "/depth", &RealsenseServer::serviceSendDepthImageStatic, this);
    serviceCaptureRGB = n.advertiseService(baseService + "/rgb", &RealsenseServer::serviceSendRGBImageStatic, this);
    serviceUVStatic = n.advertiseService(baseService + "/pointcloud/static/uv", &RealsenseServer::serviceGetUVStatic, this);
    servicePointCloudStatic = n.advertiseService(baseService + "/pointcloud/static", &RealsenseServer::serviceGetPointCloud, this);

    pubPointCloudGeometryStatic = n.advertise<sensor_msgs::PointCloud2>(baseService + "/pointcloudGeometry/static", 1);
    pubStaticRGB = n.advertise<sensor_msgs::Image>(baseService + "/rgb/static", 1);
    pubStaticDepth = n.advertise<sensor_msgs::Image>(baseService + "/depth/static", 1);
    pubPointCloudGeometryStaticRGB = n.advertise<std_msgs::Float32MultiArray>(baseService + "/pointcloudGeometry/static/rgb", 1);

    cfg.enable_stream(RS2_STREAM_COLOR, cam_width, cam_height, RS2_FORMAT_BGR8, 30);
    cfg.enable_stream(RS2_STREAM_DEPTH, cam_width, cam_height, RS2_FORMAT_Z16, 30);
}

void RealsenseServer::initializeRealsense(){
    std::cout << "initialize" << std::endl;
    startup = true;
    pipe.start(cfg);
    //RealsenseServer::update();
    //HIGH ACCURACY PRESET EXPLAINED -https://dev.intelrealsense.com/docs/d400-series-visual-presets
    //DO WE STILL WANT THIS?

    //while (ros::ok()) {
      //RealsenseServer::update();
    //}
}

void RealsenseServer::update(){
    if (startup == true){
      //Drop startup frames
      for(int i = 0; i < 50; i++){
        frames = pipe.wait_for_frames();
      }
      startup = false;
    } else {
      frames = pipe.wait_for_frames();
    }

    //rs2::frame frame = frames.first(RS2_STREAM_DEPTH);
    auto frame_depth = frames.get_depth_frame();
    auto frame_color = frames.get_color_frame();
    //Might be worth investigating how this filter influences quality of our pointcloud

    if (frame_depth && frame_color){
      // ALIGN THE STREAMS
      rs2::align align(RS2_STREAM_COLOR);
      aligned_frames = align.process(frames);

      rs2::hole_filling_filter hole_filter(2);
      rs2::decimation_filter dec_filter;
      rs2::threshold_filter thr_filter;
      // filter settings CHANGE AS NEEDED
      thr_filter.set_option(RS2_OPTION_MIN_DISTANCE, 0.3f);
      thr_filter.set_option(RS2_OPTION_MAX_DISTANCE, 2.0f);

      processed_frame = hole_filter.process(dec_filter.process(thr_filter.process(aligned_frames.get_depth_frame())));
      //rs2::depth_frame filteredDepthFrame = hole_filter.process(dec_filter.process(thr_filter.process(aligned_frames.get_depth_frame())));
      rs2::depth_frame filteredDepthFrame(processed_frame);
      float dist_to_center = filteredDepthFrame.get_distance(filteredDepthFrame.get_width()/2, filteredDepthFrame.get_height()/2);
      std::cout << "The camera is facing an object " << dist_to_center << " meters away" << std::endl;
        // GET POINTCLOUD
      RealsenseServer::generatePointcloud();
    }
}

void RealsenseServer::generatePointcloud(){
  //https://github.com/Resays/xyz_rgb_realsense/tree/master
  rs2::depth_frame depth(processed_frame);
  rs2::video_frame color(processed_frame);
  points = pc.calculate(depth);
  pc.map_to(color);
  //uv = points.get_texture_coordinates();
  auto uv_temp = points.get_texture_coordinates();
  std::cout<<"temp test "<<(float) uv_temp[8999].v<<std::endl;



}


int main(int argc, char **argv)
{
  ros::init(argc, argv, "realsense_service_cpp_node");

  RealsenseServer camera;
  camera.initializeRealsense();
  camera.update();

  ros::Rate loop_rate(30);
  while(ros::ok()){
    ros::Time time_now = ros::Time::now();
    //std::cout<<"Sending: " << time_now <<std::endl;
    ros::spinOnce();
    loop_rate.sleep();
  }

  return 0;
}
