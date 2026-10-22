# My glove won't connect / It hangs on "Blocking program until x gloves connected"

## Step 1, make sure you install the driver.
### Windows
For Windows, install the WinUSB driver: [Zadig](https://zadig.akeo.ie/). Linux does not require a driver.

   * Open this, with the glove plugged in
   * Select R1 (Composite Parent, Interface 0 or similar) in the dropdown. Don't change any other settings. Click Install Driver.

### Linux
No driver is required. However, to allow non-root access to the R1 over USB, you need to add a custom udev rule.

Run this script from the software packages.

```bash
./scripts/install_udev_rule.sh
```

OR manually:

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", ATTR{idProduct}=="10f3", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-r1-glove.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## Step 2, check the device shows up.
If it is not appearing when executing below instructions, check you used the correct power supply and cables of the correct specs. If this is is not done properly, the glove can disable itself. See [Getting started](./getting_started.md)
### Linux
```bash
lsusb
```
Should print for example:
```Bus 003 Device 019: ID 2e8a:10f3 SenseGlove R1```

### Windows
On Windows > Device Manager
Under Universal Serial Bus Devices, it should show "R1" if a glove is connected.

