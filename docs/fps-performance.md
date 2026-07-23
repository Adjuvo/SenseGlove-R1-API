



# Why is my force feedback jittering? Tips to improve it
Active haptic feedback (motorized feedback) of the glove works by getting the tracking data, then sending a force back to the glove based on that tracking data. Now there will always be a tiny bit of delay between those. If that delay becomes larger than a few ms, you get the problem where the force isn't engaged fast enough to respond to the movements, and that **will result in instability (jittering), usually on/near contact**.

```
 user closes fingers ->
 robot hand touches object and detects force -> 
 force on glove pulls users finger back -> 
 robot finger opens -> 
 robot hand doesn't detect force anymore -> 
 users finger is no longer stopped -> 
 user closes fingers -> 
 and the whole loop restarts
```
This can happen fast, causing the jittering at touching surfaces. You can fix this in a couple of ways.

1. First, make sure your commanded forces look smooth over time. You can use Teleplot (VScode extension) to quickly plot this. 

If not, be careful with using filtering, since this can cause latency. Plot the filtered values in one plot with the original signal so you can see the caused latency. Latency can also cause instability, so keep it to a minimum.

If the input smooth, some further options:

- Increasing the FPS (frames/second) of the data and reducing the latency between the glove's position update given and force received. The faster this runs, the less delay between touch and detection is, and smoother the changes in force will be. That prevents jitter. This is the best but often most difficult option. 
- Lower the forces (causes a more gradual change in force, so the finger is not harshly janked back on the object touch).
- Reduce how quickly the force responds (for example with a low pass filter, dampening, or a controller on top). This will smooth the signal and cause a more gradual buildup/reduction of force.

Fixing this with the third option might cause:
- A solid surface to feel more squishy instead of solid. (Due to less sudden force changes.)
- Less transparency on no forces (meaning how much you feel the force when there should be no force at all).


# Delay / Latency related issues
Aside from FPS, latency can cause the force feedback to respond too late to the users actions. 
```
User moves glove -> tracking sent to robot hand -> robot hand moves -> force sensor robot hand touches -> detected force sent to R1 glove -> R1 pulls users finger back.
```
If any step in this process is delayed, the users finger is pulled back too late, and the users hand (and therefore also the robot hand) will close further than it should before fingers are stopped. 

If this is at a specific frequency, it can also cause a feedback loop of instability, similar to the one for FPS, but slower.

The R1 has low latency, however, for prototypes with jitter we have added an optional smoothing filter on the tracking that might cause some slight delay as well. This is enabled by default. This might be visible as a tiny delay on the virtual glove moving compared to your real hand. You can disable this by calling the following just after SG_main.init.
```python
SG_main.init(....)
SG_main.set_filter(hand_id,  SG_T.Filter_type.SUSPICION,  0)
```
With the smoothing disabled (0) there should be no additional delay aside from when it actually detects jitter in the SUSPICION filter, so you can keep that SUSPICION filter on. If you fully want to use raw data without any jitter detection, change to `SG_T.Filter_type.OFF`.

However, in our experience, the culprit of the noticable force feedback delays is often the force sensor on the robot hand taking too long before it detected something, and for noticable movement delay, the robot hand reacting slow to a command.




# How to measure data rates
## FPS (frames per second)
Our API logs the update rate to the log files. So you can check those in `Rembrandt_API/logs/`. Or alternatively, use the SG_FPS script to quickly log your FPS at a certain point in your code.
```python
from SG_API import SG_FPS

fps_my_function = SG_FPS.FPSCounter(1.0, "my_function")

def my_function():
    global fps_my_function
    fps_my_function.update() #updates, and every 1.0 seconds prints my_function FPS
```
# What works to keep glove data >1kHz.

## Our data uses >1kHz callbacks, but your code can slow it down!
Data in our API comes in through callbacks when new data is received. These are fast, but only if your program doesn't steal their processing time!

## Don't use busy while loops 
```python
while(True)
    #do something, or nothing
    pass
```
This is a busy while loop. While it looks like it shouldn't do anything, this eats up all CPU power of the program, meaning the callbacks of the data will no longer be called at 1kHz. It can get as bad as only receiving data at 50 Hz.

```python
import time

while(True)
    #do something, or nothing
    time.sleep(1) # sleep 1 second
    pass
```
This is a non-busy while loop. During this sleep time other parts of the program are allowed to execute, such as the data callbacks needed at 1kHz.
Don't reduce this sleep time too much or it will become a more and more busy while loop.

We recommend instead of using a while loop yourself, to use `SG_main.keep_program_running()`. This internally uses this while loop system to keep the program alive, but also allows closing down smoothly with Ctrl+C, and still allow high data callbacks.

## Making things faster in python
We recommend [VTune by Intel](https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler.html) to profile your code to find the parts taking the longest. Profile your code with Hot Spots setting, and use the Bottom-up tab to find your bottleneck.



### Threading vs multiprocessing, should you use it?
Threading in python works very different from in other programs. Even with threading, only one block of python can run at a time, so it is not parallel. However, I/O or C++ calls can run simultaneously with a python thread. So good for C++/file writing, but for pure python nothing will actually run in parallel, only sequential, AND it add an overhead, so is often slower.

Multiprocessing in python is true parallelism, but harder to implement, and a lot of overhead on making the actual threads.

## Don't put too much processing in the new_data_callback
If you do, that obviously causes it to be slower, and the callback not to be called often enough. So improve your code performance by profiling if that's an issue. What helped for us it to move computationally heavy things to CPP and call them from python.

## print() can reduce fps
Don't call them continuously in the main update loop, only print every few seconds.


