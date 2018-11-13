# QRGA

This project uses genetic algorithms to create QR codes which look like desired target images (e.g., company / product logo).

![Target](examples/crow.png?raw=true "Target Image")
![Mask](examples/crow-mask.png?raw=true "Target Mask")
![Output](examples/crow-qr.png?raw=true "Output Image")

## Prerequisites

This project uses the `zbarimg` and `qrencode` tools (i.e., the `zbar-tools` and `qrencode` packages in Ubuntu).  Additionally, the following are imported by the Python3 script:
```
import argparse
import math
import subprocess
import os
import time
import warnings
import imageio
import numpy
from skimage import transform
import dask
from dask.diagnostics import ProgressBar
import threading
import tkinter
from PIL import Image, ImageTk
```

This might help:
```
pip install argparse imageio numpy dask distributed psutil scikit-image tkinter
```

## Running

Example runline:

```
python qrga.py --target crow.png --mask crow-mask.png --output crow-qr.png --data 'http://www.aaronvose.net' --validate 2 --gui
```

## Authors

* **Aaron Vose** - *Initial work* - [aaronvose.net](http://www.aaronvose.net)

## License

This project is licensed under the GPLv3 License - see the [LICENSE.md](LICENSE.md) file for details
