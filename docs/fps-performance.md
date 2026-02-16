# Why is my glove force jittering? Tips to improve it
Active haptic feedback (motorized feedback) of the glove works by getting the tracking data, then sending a force back to the glove based on that tracking data. Now there will always be a tiny bit of delay between those. If that delay becomes larger than a few ms, you get the problem where the force isn't engaged fast enough to respond to the movements, and that **will result in instability (jittering), usually on/near contact**.

You can fix this in a couple of ways.

1. First, make sure your commanded forces look smooth over time. You can use Teleplot (VScode extension) to quickly plot this. 

If not, be careful with filtering for latency. Plot the filtered in one plot with the original signal so you can see the caused latency. Latency can also cause instability, so keep it to a minimum.

If the input smooth, some further options:

- Increasing the FPS (frames/second) of the data and reducing the latency between the glove's position update given and force received. 
- Lower the forces
- Reduce how quickly the force responds (for example with a low pass filter, dampening, or a controller on top). This will smooth the signal and cause a more gradual buildup/reduction of force.

Fixing this with the third option might cause:
- A solid surface to feel more squishy instead of solid. (Due to less sudden force changes.)
- Less transparency on no forces (meaning how much you feel the force when there should be no force at all).


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
We recommend VTune by Intel to profile your code to find the parts taking the longest. 



### Threading vs multiprocessing, should you use it?
Threading in python works very different from in other programs. Even with threading, only one block of python can run at a time, so it is not parallel. However, I/O or C++ calls can run simultaneously with a python thread. So good for C++/file writing, but for pure python nothing will actually run in parallel, only sequential, AND it add an overhead, so is often slower.

Multiprocessing in python is true parallelism, but harder to implement, and a lot of overhead on making the actual threads.

## Don't put too much processing in the new_data_callback
If you do, that obviously causes it to be slower, and the callback not to be called often enough. So improve your code performance by profiling if that's an issue. What helped for us it to move computationally heavy things to CPP and call them from python.

## print() can reduce fps
Don't call them continuously in the main update loop, only print every few seconds.

