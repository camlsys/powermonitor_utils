# PowerMonitor Utils
A high-level wrapper around Monsoon Power Monitor's Python API ([PyMonsoon](https://github.com/msoon/PyMonsoon)).

## Installation
A `pip install monsoon` is probably all you need but you can also replicate the Conda environment I've used:
```bash
conda env create -f environment.yml
source activate powermonitor
```

## Requirements
If you're using a first generation Power Monitor (i.e. the white one) you'll probably need to upgrade its firmware before you can use the Python interface. The firmwares images are available in PyMonsoon's [repository](https://github.com/msoon/PyMonsoon) and are committed here as well for ease of use:

```python
from pmutils import PowerMonitor
PowerMonitor.upgrade_white_device_firmware()
```

```python
from pmutils import PowerMonitor
PowerMonitor.downgrade_white_device_firmware()
```

## Usage

```python
from pmutils import PowerMonitor

with PowerMonitor() as pm:
    pm.power_on(vout=5.0)
    pm.enable_all_channels()
    pm.live()
```

- [ ] List all useful commands.
