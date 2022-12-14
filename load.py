import numpy as np
from PIL import Image
import numpy as np
import habitat_sim
from habitat_sim.utils.common import d3_40_colors_rgb
import cv2
import json
import csv
import math
from argparse import ArgumentParser


def transform_rgb_bgr(image):
    return image[:, :, [2, 1, 0]]

def transform_depth(image):
    depth_img = (image / 10 * 255).astype(np.uint8)
    return depth_img

def transform_semantic(semantic_obs):
    semantic_img = Image.new("P", (semantic_obs.shape[1], semantic_obs.shape[0]))
    semantic_img.putpalette(d3_40_colors_rgb.flatten())
    semantic_img.putdata((semantic_obs.flatten() % 40).astype(np.uint8))
    semantic_img = semantic_img.convert("RGB")
    semantic_img = cv2.cvtColor(np.asarray(semantic_img), cv2.COLOR_RGB2BGR)
    return semantic_img

 


def make_simple_cfg(settings, action_list):
    # simulator backend
    sim_cfg = habitat_sim.SimulatorConfiguration()
    sim_cfg.scene_id = settings["scene"]
    

    # In the 1st example, we attach only one sensor,
    # a RGB visual sensor, to the agent
    rgb_sensor_spec = habitat_sim.CameraSensorSpec()
    rgb_sensor_spec.uuid = "color_sensor"
    rgb_sensor_spec.sensor_type = habitat_sim.SensorType.COLOR
    rgb_sensor_spec.resolution = [settings["height"], settings["width"]]
    rgb_sensor_spec.position = [0.0, settings["sensor_height"], 0.0]
    rgb_sensor_spec.orientation = [
        settings["sensor_pitch"],
        0.0,
        0.0,
    ]
    rgb_sensor_spec.sensor_subtype = habitat_sim.SensorSubType.PINHOLE

    #semantic snesor
    semantic_sensor_spec = habitat_sim.CameraSensorSpec()
    semantic_sensor_spec.uuid = "semantic_sensor"
    semantic_sensor_spec.sensor_type = habitat_sim.SensorType.SEMANTIC
    semantic_sensor_spec.resolution = [settings["height"], settings["width"]]
    semantic_sensor_spec.position = [0.0, settings["sensor_height"], 0.0]
    semantic_sensor_spec.orientation = [
        settings["sensor_pitch"],
        0.0,
        0.0,
    ]
    semantic_sensor_spec.sensor_subtype = habitat_sim.SensorSubType.PINHOLE

    # agent
    agent_cfg = habitat_sim.agent.AgentConfiguration()

    agent_cfg.sensor_specifications = [rgb_sensor_spec, semantic_sensor_spec]
    ##################################################################
    ### change the move_forward length or rotate angle
    ##################################################################
    agent_cfg.action_space = {}
    for i, action in enumerate(action_list):
        agent_cfg.action_space[i] = action

    return habitat_sim.Configuration(sim_cfg, [agent_cfg])

def target_mask(semantic_img, target_label):
    mask = np.ones((512, 512, 3))
    for u in range(semantic_img.shape[0]):
        for v in range(semantic_img.shape[1]):
            if np.array_equal(semantic_img[u][v], target_label):
                mask[u][v] = [0, 0, 255]
    return mask.astype(np.uint8)

img_list = []
def navigateAndSee(action="", target_label=None):
    if action in action_names:
        observations = sim.step(action)
        #print("action: ", action)
        img = transform_rgb_bgr(observations["color_sensor"])
        mask = target_mask(id_to_label[observations["semantic_sensor"]], target_label)
        masked_img = cv2.addWeighted(img, 0.8, mask, 0.2, 0)
        # cv2.imshow("RGB", masked_img)
        img_list.append(masked_img)
        #cv2.imshow("depth", transform_depth(observations["depth_sensor"]))
        agent_state = agent.get_state()
        sensor_state = agent_state.sensor_states['color_sensor']
        print("camera pose: x y z rw rx ry rz")
        print(sensor_state.position[0],sensor_state.position[1],sensor_state.position[2],  sensor_state.rotation.w, sensor_state.rotation.x, sensor_state.rotation.y, sensor_state.rotation.z)


parser = ArgumentParser()
parser.add_argument(
    "-t", dest="target", help="select target", type=str
)
# This is the scene we are going to load.
# support a variety of mesh formats, such as .glb, .gltf, .obj, .ply
### put your scene path ###
test_scene = "apartment_0/habitat/mesh_semantic.ply"
path = "apartment_0/habitat/info_semantic.json"

cam_ori = math.pi
navigate_path = []
with open(f"{parser.parse_args().target}_path.csv", 'r') as f:
    csvreader = csv.reader(f)
    for row in csvreader:
        for i in range(2):
            row[i] = float(row[i])
            coor = np.asarray(row[:3], dtype=np.float32)
        navigate_path.append(coor)
    f.close()

action_list = []
for i in range(1, len(navigate_path)):
    theta = math.atan2(navigate_path[i][1] - navigate_path[i - 1][1], navigate_path[i][0] - navigate_path[i - 1][0])
    if theta < 0:
        theta += 2*math.pi
    print(180*theta/math.pi)
    temp = theta
    theta -= cam_ori
    cam_ori = temp
    if theta != 0:
        action_list.append(habitat_sim.agent.ActionSpec(
                "turn_left", habitat_sim.agent.ActuationSpec(amount=180 * theta/math.pi) # 1.0 means 1 degree
            ))
    action_list.append(habitat_sim.agent.ActionSpec(
            "move_forward", habitat_sim.agent.ActuationSpec(amount=0.5) # 0.01 means 0.01 m
        ))

label_dict = {
    "refrigerator": 67,
    "rack": 66,
    "cushion": 29,
    "lamp": 47,
    "cooktop": 32 
    }

#global test_pic
#### instance id to semantic id 
with open(path, "r") as f:
    annotations = json.load(f)

id_to_label = []
instance_id_to_semantic_label_id = np.array(annotations["id_to_label"])
for i in instance_id_to_semantic_label_id:
    if i < 0:
        id_to_label.append(0)
    else:
        id_to_label.append(i)
id_to_label = np.asarray(id_to_label)

######

sim_settings = {
    "scene": test_scene,  # Scene path
    "default_agent": 0,  # Index of the default agent
    "sensor_height": 1.5,  # Height of sensors in meters, relative to the agent
    "width": 512,  # Spatial resolution of the observations
    "height": 512,
    "sensor_pitch": 0,  # sensor pitch (x rotation in rads)
}

# This function generates a config for the simulator.
# It contains two parts:
# one for the simulator backend
# one for the agent, where you can attach a bunch of sensors

cfg = make_simple_cfg(sim_settings, action_list)
sim = habitat_sim.Simulator(cfg)


# initialize an agent
agent = sim.initialize_agent(sim_settings["default_agent"])

# Set agent state
agent_state = habitat_sim.AgentState()
agent_state.position = np.array([navigate_path[0][1], 0.0, navigate_path[0][0]])  # agent in world space
agent.set_state(agent_state)

# obtain the default, discrete actions that an agent can perform
# default action space contains 3 actions: move_forward, turn_left, and turn_right
action_names = list(cfg.agents[sim_settings["default_agent"]].action_space.keys())
print("Discrete action space: ", action_names)


# FORWARD_KEY="w"
# LEFT_KEY="a"
# RIGHT_KEY="d"
# FINISH="f"
# print("#############################")
# print("use keyboard to control the agent")
# print(" w for go forward  ")
# print(" a for turn left  ")
# print(" d for trun right  ")
# print(" f for finish and quit the program")
# print("#############################")

target_label = label_dict[parser.parse_args().target]


for i in range(len(action_list) - 1):
    action = i
    navigateAndSee(i, target_label)    
    # keystroke = cv2.waitKey(0)
    # if keystroke == ord(RIGHT_KEY):
    #     continue

# while True:
#     keystroke = cv2.waitKey(0)
#     if keystroke == ord(FINISH):
#         print("action: FINISH")
#         break
#     else:
#         print("INVALID KEY")
#         continue    

out = cv2.VideoWriter(f'results/{parser.parse_args().target}.avi', cv2.VideoWriter_fourcc('M','J','P','G'), 3, (512, 512))
while img_list:
    img = img_list.pop(0)
    cv2.imshow("img", img)
    cv2.waitKey(333)
    out.write(img)
out.release()