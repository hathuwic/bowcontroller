# BOWCONTROLLER

Watch the demo video: https://drive.google.com/file/d/1PwbykmJccvtBl9BjLUUu1WIoxm4yglWo/view?usp=sharing

---

## To run the project:

1. On the Portal MoCap PC, start Motive and calibrate the OptiTrack system.
2. Set up two rigid bodies. The system is intended and calibrated to use a violin and bow, but you can theoretically use any two rigid bodies provided one has ID 1 and the other has ID 2.
3. Connect your laptop to the Cisco network switch located behind the MoCap PC via ethernet. This allows your laptop to communicate with the MoCap PC.
4. Open the Data Streaming panel in Motive and ensure streaming is on, and sending out via the IP address (i.e., not in loopback mode).
5. In the terminal create or load an Anaconda environment and install the following packages:
	- Numpy (pip install numpy)
	- Scipy (pip install scipy)
	- PythonOSC (pip install python-osc)
6. Navigate your terminal to the project root folder (where this readme is located) and run the command 'python feature_extraction.py' to run the Python script.
7. Open main_patch.maxpat. If the Python script is running, the patch should automatically be receiving data via OSC.
8. Wave your rigid bodies around the capture space. If you see the numbers changing and graphs moving, you're nearly there.
9. To load a MIDI file, drag and drop it into the box in the top left of the presentation view of the Max patch.
	- Recommended test file: ./MIDI_files/test_accomp_longer.mid -> this is the one used in the demo video
10. Click 'Start Playback' and playback should start. Move the rigid bodies while it's playing to see what happens. Your results with non-violin and -bow shaped rigid bodies may vary!

---

Troubleshooting:

- If the Python script can't find the MoCap PC:
	- Ensure Motive is running, data streaming is on, and it's not in loopback mode.
	- Check your IP as connected to the Cisco network switch.
		- Run the 'ipconfig' command, look for the UiO network in the list, and check your IP address is the same as that listed in the Python script on line 288.
		- If not, change it to your IP in the script.
- If the Python script is running correctly but the Max patch isn't receiving any data over OSC:
	- The Python script and Max patch should be running on the same machine, as the OSC is set to use localhost.
	- Check that the port in the Python script (line 280) and in the Max patch (top left in the patcher when not in presentation view) are the same.

---

Included files:

- feature_extraction.py		-> the main Python script receiving data from Motive, extracting features, and sending to Max via OSC
- main_patch.maxpat		-> the main Max patch containing the OSC receiver, parameter mapping, and synthesiser
- bowed_string_voice.maxpat	-> the patch for one voice of the synthesiser, used in the poly~ object to make a polysynth
- MIDI_files folder		-> the directory for the test MIDI files for the Max patch
- README.txt			-> this document
- DataDescriptors.py		-> part of the NatNet SDK provided by OptiTrack - DO NOT MODIFY
- MoCapData.py			-> part of the NatNet SDK provided by OptiTrack - DO NOT MODIFY
- NatNetClient.py		-> part of the NatNet SDK provided by OptiTrack - DO NOT MODIFY