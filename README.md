# Generating appropriate object orientations for robot-to-human handovers using synthetic object affordances 10th semester project
Masther thesis 

By Albert Daugbjerg Christensen and Daniel Lehotský

Aalborg University (2022)

Electronics and IT

Supervisor: Dimitris Chrysostomou


## Links to affiliated repositories

The dataset generator implemented in the Unity game engine can be found here: https://github.com/HuchieWuchie/affordanceSynthetic
The analysis of the human-to-human handover dataset can be found here: https://github.com/daniellehot/handover_orientation_analysis 

## Description

This repository contains our ROS node implementation master thesis "Generating appropriate object orientations for robot-to-human handovers using synthetic object affordances". The system is capable of performing task-oriented handovers, where an object is grasped by its functional affordance and handover with an appropriate orientaiton. Object affordances are detected using our deep neural network AffNet-DR, which was trained solely on synthetic data. A synthetic dataset already generated can be downloaded from here https://drive.google.com/file/d/1yRL2JbZhZEsL2O9fKbM_DDJ7U53dogkl/view?usp=sharing .

https://user-images.githubusercontent.com/34643562/171363846-6cac8411-6d7b-4615-86e1-b2e0edf9657b.mp4

## Requirements:

General system requirements
```
CUDA version 11.6
NVIDIA GPU driver 510.60.02
ROS melodic
ros-melodic-moveit
ros-melodic-urg-node
```

C++:
```
realsense2
PCL (point cloud library)
OpenCV
```

Python 3.6.9
```
open3d 0.15.2
cv2 4.2.0
numpy 1.19.5
scipy 1.5.4
scikit_learn 0.24.2
torch (Pytorch) 1.10.2 cuda version
torchvision 0.11.2 cuda
scikit_image 0.17.2
PIL 8.4.0
rospkg 1.4.0
```

The system ran on a Lenovo Thinkpad P53 laptop with a Quadro RTX 4000 GPU with 8 GB VRAM and an Intel Core i9-9880H CPU 2.3 GHZ and 32 GB RAM.


## Installation:
```
mkdir ros_ws
mkdir ros_ws/src
cd ros_ws/src

git clone https://github.com/IFL-CAMP/iiwa_stack.git
git clone https://github.com/ros-industrial/robotiq.git
git clone https://github.com/daniellehot/ROB10.git

cd ..
catkin_make
source devel/setup.bash
```

Download pretrained weights from: https://drive.google.com/file/d/1psCn_aT5KUyQDJrdxqR7GJgHeCewGokS/view?usp=sharing

Place and rename the weights file to ros_ws/src/affordanceAnalyzer/scripts/affordance_synthetic/weights.pth

## Setup the KUKA LBR iiwa 7 R800:

Install the iiwa stack found here: https://github.com/IFL-CAMP/iiwa_stack
Run the ROSSmartservo package on the KUKA controller, do this after launching ros on your ROS pc.

## Setup of the ROS pc:

Connect an ethernet cable between the ROS pc and the KUKA sunrise controller. Setup the network configuration on your ROS pc to the following:

```
IP: 172.31.1.150
Netmask: 255.255.0.0
```

Export ros settings 
```
export ROS_IP=172.31.1.150
export ROS_MASTER_URI=http://172.31.1.150:11311
```

Modify permission for the laser scanner
```
sudo chmod a+rw /dev/ttyACM0      # note that the usb port might change
```

## Usage 

launch roscore and launch file
```
source devel/setup.bash
roscore
roslaunch iiwa_noPtu_moveit moveit_planning_execution.launch
```

Launch whatever experiement you want, chose between the ones listed below.
```
rosrun rob10 final_test_observation.py
rosrun rob10 final_test_rule.py
rosrun rob10 orientation_test_observation.py # user study on orientation methods
rosrun rob10 orientation_test_rule.py
rosrun rob10 orientation_test_random.py
```

In order to command the robot to pick up an object you must send a command to the rostopic /objects_affordances_id. The integer id corresponds to the object classes of AffNet-DR, eg. 1 (knife), 16 (mallet), etc.

Note if you want to run the orientation_test_METHOD.py scripts you have to make use of precomputed information which can be found at: https://drive.google.com/file/d/1OhkOdDlKzmiacBYNIeN8ccKTg_f816GE/view?usp=sharing
