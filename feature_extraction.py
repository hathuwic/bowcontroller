"""
-------------------------------------------------
MCT4053 Project
PYTHON SCRIPT
Receives rigid body data from Motive, stores data and extracts features, send to Max via OSC.
-------------------------------------------------
Candidate Number: 177
"""

# Imports
import sys
import time
from NatNetClient import NatNetClient
import DataDescriptions
import MoCapData
import numpy as np
import time

from pythonosc import udp_client

from scipy.spatial.transform import Rotation

# Specify Motive framerate setting
framerate = 120

# ------------------------------------------------------------

# Define Bow class to contain the violin's current position and rotation, and the 6 most recent frames.
class Violin():
    def __init__(self):
        self.history_length = 6
        
        self.current_position = np.zeros((3, 1))
        self.current_rotation = np.ones((4, 1))
        self.position_history = np.zeros((3, self.history_length))
        self.rotation_history = np.ones((4, self.history_length))
        
    def update_position(self, position):
        """Update stored postion and position history."""
        for i in range(3):
            self.current_position[i] = position[i]
        self.position_history = np.append(self.position_history, self.current_position, axis=1)[:, 1:]
        
    def update_rotation(self, rotation):
        """Update stored rotation and rotation history."""
        for i in range(4):
            self.current_rotation[i] = rotation[i]
        self.rotation_history = np.append(self.rotation_history, self.current_rotation, axis=1)[:, 1:]


# Define Violin class to contain bow's current position and rotation, recent position and rotation history,
# and relative position, rotation, velocity, and acceleration
class Bow():
    def __init__(self):
        self.history_length = 6
        
        self.current_position = np.zeros((3, 1))
        self.current_rotation = np.ones((4, 1))
        self.position_history = np.zeros((3, self.history_length))
        self.rotation_history = np.ones((4, self.history_length))
        
        self.relative_position_violin_axes = np.zeros((3, 1))
        self.relative_position_global_axes = np.zeros((3, 1))
        self.relative_rotation = np.ones((3, 1))
        self.relative_position_history = np.zeros((3, self.history_length))
        self.relative_rotation_history = np.ones((4, self.history_length))
        
        self.relative_velocity = np.zeros((3, 1))
        self.relative_velocity_history = np.zeros((3, self.history_length))
        self.relative_acceleration = np.zeros((3,1))
    
    def update_position(self, position, violin):
        """Update stored absolute position, and position relative to violin."""
        for i in range(3):
            self.current_position[i] = position[i]
        self.position_history = np.append(self.position_history, self.current_position, axis=1)[:, 1:]
        
        # Create violin rotation object
        violin_rotation = Rotation.from_quat(violin.current_rotation.flatten())
        # Get bow position relative to violin, in global axes
        self.relative_position_global_axes = violin.current_position - self.current_position
        # Dot product of relative position and violin rotation matrix to get relative position in axes of violin
        self.relative_position_violin_axes = np.dot(self.relative_position_global_axes.flatten(), violin_rotation.as_matrix())
        self.relative_position_history = np.append(self.relative_position_history, self.relative_position_violin_axes.reshape(-1,1), axis=1)[:, 1:]
        
    def update_rotation(self, rotation, violin):
        """Update stored absolute rotation, and rotation relative to violin."""
        # Update current rotation quat values to those provided in frame
        for i in range(4):
            self.current_rotation[i] = rotation[i]
        # Append new rotation to rotation history and drop the first frame to retain history length
        self.rotation_history = np.append(self.rotation_history, self.current_rotation, axis=1)[:, 1:]
        
        # Create rotation objects to allow for calculating difference between them
        violin_rotation = Rotation.from_quat(violin.current_rotation.flatten())
        bow_rotation = Rotation.from_quat(self.current_rotation.flatten())
        # Temp rotation object describing relationship between violin and bow
        relative_rotation_temp = violin_rotation * bow_rotation.inv()
        # Attribute (for OSC) as euler angle
        self.relative_rotation = relative_rotation_temp.as_euler("xyz")
        self.relative_rotation_history = np.append(self.relative_rotation_history, relative_rotation_temp.as_quat().reshape(-1,1), axis=1)[:, 1:]
        
    def update_relative_velocity(self):
        """Update relative velocity of bow to violin, given relative position history."""
        for i, axis in enumerate(self.relative_position_history): # Looping through axes i.e., xyz
            self.relative_velocity[i] = np.ediff1d(axis).mean() * framerate # Mean of difference between points * framerate = distance per second in metres
        
        self.relative_velocity_history = np.append(self.relative_velocity_history, self.relative_velocity.reshape(-1,1), axis=1)[:, 1:]

    def update_relative_acceleration(self):
        """Update relative acceleration history given relative velocity history."""
        for i, axis in enumerate(self.relative_velocity_history):
            self.relative_acceleration[i] = np.ediff1d(axis).mean() * framerate # Mean of difference between velocities * framerate = accel in m/s^2

# ----------------------------------------------------------

# Not used
def receive_new_frame(data_dict):
    order_list=[ "frameNumber", "markerSetCount", "unlabeledMarkersCount", "rigidBodyCount", "skeletonCount",
                "labeledMarkerCount", "timecode", "timecodeSub", "timestamp", "isRecording", "trackedModelsChanged" ]
    pass


def receive_rigid_body_frame(new_id, position, rotation):
    """Main callback function called when a new rigid body frame is received. Updates the stored values
    for the given body (violin or bow), and sends values to Max over OSC when a bow frame is received."""

    frame_start = time.time()
    
    # Violin rigid body with ID 1
    if new_id == 1: 
        # Update attributes of Violin object
        violin.update_rotation(rotation)
        violin.update_position(position)
    
    # Bow rigid body with ID 2
    elif new_id == 2: 
        # Update attributes of Bow object
        bow.update_rotation(rotation, violin)
        bow.update_position(position, violin)
        bow.update_relative_velocity()
        bow.update_relative_acceleration()
    
    # Error case for unrecognized rigid body ID
    else:
        print("Unexpected rigid body ID:", new_id, "   Pos:", position, "   Rot:", rotation)
    
    # Sending current values over OSC when ID 2 i.e., bow is received
    if new_id == 2:
        # Sending current absolute position and rotation of each body
        oscClient_local.send_message("/vln_pos", violin.current_position.flatten().tolist())
        oscClient_local.send_message("/vln_rot", violin.current_rotation.flatten().tolist())
        oscClient_local.send_message("/bow_pos", bow.current_position.flatten().tolist())
        oscClient_local.send_message("/bow_rot", bow.current_rotation.flatten().tolist())
        
        # Sending relative bow pos, rot, vel, and acc relative to violin
        oscClient_local.send_message("/bow_rel_pos", bow.relative_position_violin_axes.flatten().tolist())
        oscClient_local.send_message("/bow_rel_rot", bow.relative_rotation.flatten().tolist()) #.as_euler("xyz"))
        oscClient_local.send_message("/bow_rel_vel", bow.relative_velocity.flatten().tolist())
        oscClient_local.send_message("/bow_rel_acc", bow.relative_acceleration.flatten().tolist())

    # Print time taken to update objects and send OSC messages (if applicable)
    exec_time = time.time() - frame_start
    print(f"Frame exec time: {exec_time}")


def add_lists(totals, totals_tmp):
    totals[0]+=totals_tmp[0]
    totals[1]+=totals_tmp[1]
    totals[2]+=totals_tmp[2]
    return totals


def print_configuration(natnet_client):
    print("Connection Configuration:")
    print("  Client:          %s"% natnet_client.local_ip_address)
    print("  Server:          %s"% natnet_client.server_ip_address)
    print("  Command Port:    %d"% natnet_client.command_port)
    print("  Data Port:       %d"% natnet_client.data_port)

    if natnet_client.use_multicast:
        print("  Using Multicast")
        print("  Multicast Group: %s"% natnet_client.multicast_address)
    else:
        print("  Using Unicast")

    #NatNet Server Info
    application_name = natnet_client.get_application_name()
    nat_net_requested_version = natnet_client.get_nat_net_requested_version()
    nat_net_version_server = natnet_client.get_nat_net_version_server()
    server_version = natnet_client.get_server_version()

    print("  NatNet Server Info")
    print("    Application Name %s" %(application_name))
    print("    NatNetVersion  %d %d %d %d"% (nat_net_version_server[0], nat_net_version_server[1], nat_net_version_server[2], nat_net_version_server[3]))
    print("    ServerVersion  %d %d %d %d"% (server_version[0], server_version[1], server_version[2], server_version[3]))
    print("  NatNet Bitstream Requested")
    print("    NatNetVersion  %d %d %d %d"% (nat_net_requested_version[0], nat_net_requested_version[1],\
       nat_net_requested_version[2], nat_net_requested_version[3]))


def print_commands(can_change_bitstream):
    outstring = "Commands:\n"
    outstring += "Return Data from Motive\n"
    outstring += "  s  send data descriptions\n"
    outstring += "  r  resume/start frame playback\n"
    outstring += "  p  pause frame playback\n"
    outstring += "     pause may require several seconds\n"
    outstring += "     depending on the frame data size\n"
    outstring += "Change Working Range\n"
    outstring += "  o  reset Working Range to: start/current/end frame = 0/0/end of take\n"
    outstring += "  w  set Working Range to: start/current/end frame = 1/100/1500\n"
    outstring += "Return Data Display Modes\n"
    outstring += "  j  print_level = 0 supress data description and mocap frame data\n"
    outstring += "  k  print_level = 1 show data description and mocap frame data\n"
    outstring += "  l  print_level = 20 show data description and every 20th mocap frame data\n"
    outstring += "Change NatNet data stream version (Unicast only)\n"
    outstring += "  3  Request 3.1 data stream (Unicast only)\n"
    outstring += "  4  Request 4.0 data stream (Unicast only)\n"
    outstring += "t  data structures self test (no motive/server interaction)\n"
    outstring += "c  show configuration\n"
    outstring += "h  print commands\n"
    outstring += "q  quit\n"
    outstring += "\n"
    outstring += "NOTE: Motive frame playback will respond differently in\n"
    outstring += "       Endpoint, Loop, and Bounce playback modes.\n"
    outstring += "\n"
    outstring += "EXAMPLE: PacketClient [serverIP [ clientIP [ Multicast/Unicast]]]\n"
    outstring += "         PacketClient \"192.168.10.14\" \"192.168.10.14\" Multicast\n"
    outstring += "         PacketClient \"127.0.0.1\" \"127.0.0.1\" u\n"
    outstring += "\n"
    print(outstring)

    
def request_data_descriptions(s_client):
    # Request the model definitions
    s_client.send_request(s_client.command_socket, s_client.NAT_REQUEST_MODELDEF,    "",  (s_client.server_ip_address, s_client.command_port) )

    
def test_classes():
    totals = [0,0,0]
    print("Test Data Description Classes")
    totals_tmp = DataDescriptions.test_all()
    totals=add_lists(totals, totals_tmp)
    print("")
    print("Test MoCap Frame Classes")
    totals_tmp = MoCapData.test_all()
    totals=add_lists(totals, totals_tmp)
    print("")
    print("All Tests totals")
    print("--------------------")
    print("[PASS] Count = %3.1d"%totals[0])
    print("[FAIL] Count = %3.1d"%totals[1])
    print("[SKIP] Count = %3.1d"%totals[2])

    
def my_parse_args(arg_list, args_dict):
    # Set up base values
    arg_list_len=len(arg_list)
    if arg_list_len>1:
        args_dict["serverAddress"] = arg_list[1]
        if arg_list_len>2:
            args_dict["clientAddress"] = arg_list[2]
        if arg_list_len>3:
            if len(arg_list[3]):
                args_dict["use_multicast"] = True
                if arg_list[3][0].upper() == "U":
                    args_dict["use_multicast"] = False

    return args_dict


if __name__ == "__main__":
    # Instancing violin and bow objects, to be updated in receive_rigid_body_frame().
    violin = Violin()
    bow = Bow()

    # Setting up OSC client to send to Max on local machine.
    oscIP_local = "127.0.0.1"
    oscPort_local = 57777
    oscClient_local = udp_client.SimpleUDPClient(oscIP_local, oscPort_local)
    oscClient_local.send_message("/startup", "well hello there General Grevious")

    # -----------------------------------------------------------------------
    # Setting up NatNet client parameters - check here if not connecting

    options_dict = {}
    options_dict["clientAddress"] = "169.254.159.192" # My IP on ethernet from Cisco network adapter in the Portal
    options_dict["serverAddress"] = "129.240.79.163" # Portal Motive PC IP
    options_dict["use_multicast"] = True

    # Create new NatNet client
    streaming_client = NatNetClient()
    streaming_client.set_client_address(options_dict["clientAddress"])
    streaming_client.set_server_address(options_dict["serverAddress"])
    streaming_client.set_use_multicast(options_dict["use_multicast"])

    # Configure the streaming client to call the rigid body handler on the emulator to send data out.
    streaming_client.new_frame_listener = receive_new_frame
    streaming_client.rigid_body_listener = receive_rigid_body_frame

    # -----------------------------------------------------------------------
    # Start the NatNet client

    # Start up the streaming client now that the callbacks are set up.
    # This will run perpetually, and operate on a separate thread.
    is_running = streaming_client.run() # Returns boolean for if client is running
    print("is_running:", is_running)

    if not is_running:
        print("ERROR: Could not start streaming client.")
        try:
            sys.exit(1)
        except SystemExit:
            print("...")
        finally:
            print("Exiting")

    is_looping = True
    time.sleep(1)
    if streaming_client.connected() is False:
        print("ERROR: Could not connect properly. Check that Motive streaming is on.")
        try:
            sys.exit(2)
        except SystemExit:
            print("...")
        finally:
            print("Exiting")

    print_configuration(streaming_client)
    print("\n")
    print_commands(streaming_client.can_change_bitstream_version())


    while is_looping:
        inchars = input('Enter command or (\'h\' for list of commands)\n')
        if len(inchars)>0:
            c1 = inchars[0].lower()
            if c1 == 'h' :
                print_commands(streaming_client.can_change_bitstream_version())
            elif c1 == 'c' :
                print_configuration(streaming_client)
            elif c1 == 's':
                request_data_descriptions(streaming_client)
                time.sleep(1)
            elif (c1 == '3') or (c1 == '4'):
                if streaming_client.can_change_bitstream_version():
                    tmp_major = 4
                    tmp_minor = 0
                    if(c1 == '3'):
                        tmp_major = 3
                        tmp_minor = 1
                    return_code = streaming_client.set_nat_net_version(tmp_major,tmp_minor)
                    time.sleep(1)
                    if return_code == -1:
                        print("Could not change bitstream version to %d.%d"%(tmp_major,tmp_minor))
                    else:
                        print("Bitstream version at %d.%d"%(tmp_major,tmp_minor))
                else:
                    print("Can only change bitstream in Unicast Mode")

            elif c1 == 'p':
                sz_command="TimelineStop"
                return_code = streaming_client.send_command(sz_command)
                time.sleep(1)
                print("Command: %s - return_code: %d"% (sz_command, return_code) )
            elif c1 == 'r':
                sz_command="TimelinePlay"
                return_code = streaming_client.send_command(sz_command)
                print("Command: %s - return_code: %d"% (sz_command, return_code) )
            elif c1 == 'o':
                tmpCommands=["TimelinePlay",
                            "TimelineStop",
                            "SetPlaybackStartFrame,0",
                            "SetPlaybackStopFrame,1000000",
                            "SetPlaybackLooping,0",
                            "SetPlaybackCurrentFrame,0",
                            "TimelineStop"]
                for sz_command in tmpCommands:
                    return_code = streaming_client.send_command(sz_command)
                    print("Command: %s - return_code: %d"% (sz_command, return_code) )
                time.sleep(1)
            elif c1 == 'w':
                tmp_commands=["TimelinePlay",
                            "TimelineStop",
                            "SetPlaybackStartFrame,10",
                            "SetPlaybackStopFrame,1500",
                            "SetPlaybackLooping,0",
                            "SetPlaybackCurrentFrame,100",
                            "TimelineStop"]
                for sz_command in tmp_commands:
                    return_code = streaming_client.send_command(sz_command)
                    print("Command: %s - return_code: %d"% (sz_command, return_code) )
                time.sleep(1)
            elif c1 == 't':
                test_classes()

            elif c1 == 'j':
                streaming_client.set_print_level(0)
                print("Showing only received frame numbers and supressing data descriptions")
            elif c1 == 'k':
                streaming_client.set_print_level(1)
                print("Showing every received frame")

            elif c1 == 'l':
                print_level = streaming_client.set_print_level(20)
                print_level_mod = print_level % 100
                if(print_level == 0):
                    print("Showing only received frame numbers and supressing data descriptions")
                elif (print_level == 1):
                    print("Showing every frame")
                elif (print_level_mod == 1):
                    print("Showing every %dst frame"%print_level)
                elif (print_level_mod == 2):
                    print("Showing every %dnd frame"%print_level)
                elif (print_level == 3):
                    print("Showing every %drd frame"%print_level)
                else:
                    print("Showing every %dth frame"%print_level)

            elif c1 == 'q':
                is_looping = False
                streaming_client.shutdown()
                break
            else:
                print("Error: Command %s not recognized"%c1)
            print("Ready...\n")
    print("Exiting")