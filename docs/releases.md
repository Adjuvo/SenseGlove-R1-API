# Releases

## v0.0.24
The jitter filter is improved, and an optional smoothing filter was added to smooth out any remaining sudden jumps on recovery of signal.The jitter filter itself causes no extra delay while detecting correct data.  However, this smoothing filter causes some slight delay. See [Delay](fps-performance.md#delay--latency-related-issues) on how to disable or adjust.

## v0.0.23
- Fix for left gloves thumb abduction.
- Improved the jitter filter even further.


## v0.0.22
2026-06-15

Summary: Improved jitter filter, frames per seconds (FPS) improvements, and a breaking change for simulated gloves.

- New jitter filter that severely reduces jitter. It has less latency than the previous median 5 filter and better performance. Succesfully filters more values and FPS increased significantly.
- FPS increase for Windows PC's, more than doubling the fps on some pc's.
- Breaking change for simulated gloves: Simulation_Mode.PLAYBACK_MODE now exists. This should replace STEADY_MODE in situations where you would update the simulation exo_angles yourself, or play a recording. This is so the new_data function doesn't go off twice per sample, reducing the FPS. Make sure you replace it if you have custom scripts updating sim angles where necessary.
- Better recording implementation, now also supports recording and playback of csv's, and at higher framerates.
- By default now creates 0.5 prototype exoskeleton instead of a 0.4 for simulated glove, preventing position based mismatches .


## v0.0.21
2026-04-02

- Improved docs: Getting started, force control, and added spec sheet information.
- Turned on tracking median filter by default.


## v0.0.20
2026-03-12

Fixed serial number >= 60 having connection issues.

## v0.0.19
2026-03-06

Small readme alignment update

## v0.0.18
2026-03-06

Fixed readme's Gitlab instead of Github link, and mentioned 3.11 python support in it.

## v0.0.17
- Added support for Python 3.11.
- Added troubleshooting instructions for WSL (Windows Subsystem for Linux) installs.
- Improved Qt import error troubleshooting logs

### v0.0.16
Added Fingertip distances to SG_main.
Replaced docs links to actual Release docs.

### v0.0.15
Minor changes to the documentation. First version actually sent to customers.

### v0.0.14
Minor changes to the documentation.

### v0.0.13
Github pages update

### v0.0.12
Docs and docs for releases update.

### v0.0.11
Addition of Github pages for docs.

### v0.0.10
First formal release of the R1 API going to customers with license on Github.

### v0.0.9
First formal release of the R1 API going to customers.

