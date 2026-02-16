

## Compiling the SG_math.cpp to libSG_math.so (Linux shared lib)
upgrade your gcc version. We use gcc 9 since that runs fine on newer systems as well as old systems
For linux (.so file is for linux shared lib): `g++ -shared -o libSG_math.so -fPIC SG_math.cpp`

### Notes on libsgrembrandt.so
- Building with an older GCC (ubuntu 20, gcc-9): Will run fine on newer systems due to backwards compatibility
- Building with a newer GCC may fail on older systems (there'll be some missing symbols)
Ubuntu 20 has gcc 9 (which makes it compatible with most systems), Ubuntu 24 does not (default on demo laptop). You can use the Ubuntu 20 devcontainer to do this (see Compiling Rembrandt SDK for Ubuntu below).


## Compiling the SG_math.cpp to libSG_math.dll (Windows shared lib)
- Install git bash
- Install mysis2 https://www.msys2.org/
    - In mysis2 terminal: `pacman -S mingw-w64-ucrt-x86_64-gcc`
    - `y` to install
    - `pacman -S --needed base-devel mingw-w64-x86_64-toolchain`
    - Press Enter to select the default option, then `y`
    - Add this to your PATH environment variables **`C:\msys64\mingw64\bin`**
- Open up git bash
    - `gcc --version`  should now work
    - I wanted to compile a single cpp file to a library to import into python, so made a file and in that folder in git bash ran:
    - For windows (.dll file is for windows shared lib)`g++ -shared -o libSG_math.dll -fPIC SG_math.cpp`
    - For linux (.so file is for linux shared lib): `g++ -shared -o libSG_math.so -fPIC SG_math.cpp`
    - An SG_math.so file and .dll spawned, hurray!

Video I got it from: https://www.youtube.com/watch?v=B2WwXfo3iJw



## Compiling the Rembrandt SDK for Ubuntu

### Notes on RembrandtPySDK.so


- pybind11 shared library links the C++ SDK into Python. It must be built for the exact Python version you are using
- A .so compiled for Python 3.8 cannot be imported in Python 3.12
- But it links dynamically to the system C++ standard library (libstdc++):

Ubuntu 20 has gcc 9 (which makes it compatible with most systems), Ubuntu 24 does not.
There it also have the python 3.8 installed (also compatible with future versions).

The demo laptop (OMEN) by default has Ubuntu 24
So you need to switch to Docker container with Ubuntu 20 to compile.
Gitlab rembrandt/devcontainer: https://gitlab.com/senseglove/rembrandt/devcontainer

Follow the readme.

Open in vscode, Ctrl Shift P, open Dev Containers: Rebuild and open in Container.
Then you have your terminal in it
And left bottom green bar Dev Container


ls in /workspace of the terminal (should be your current folder)

go to rembrandt-sdk

```
make clean

make
```

The stage folder will have the shared .so libs to copy to the API CPPlibs folder
build/tests will have all rembrandt-client compiles etc. 
If you want to run that:

Ctrl shift P
Dev Containers > Reopen folder locally
You are now out of the container.

Open tests in terminal (you can right click on it in vscode open terminal)
./rembrandt-client
to run it.


