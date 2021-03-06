# QRGA

This project uses genetic algorithms to create QR codes which look like desired target images (e.g., company / product logo).

![Target](examples/crow.png?raw=true "Target Image")
![Mask](examples/crow-mask.png?raw=true "Target Mask")
![Output](examples/crow-qr.png?raw=true "Output Image")

![Target](examples/btc.png?raw=true "Target Image")
![Mask](examples/btc-mask.png?raw=true "Target Mask")
![Output](examples/btc-qr.png?raw=true "Output Image")

![Target](examples/ornament.png?raw=true "Target Image")
![Mask](examples/ornament-mask.png?raw=true "Target Mask")
![Output](examples/ornament-qr.png?raw=true "Output Image")

![Target](examples/unicorn.png?raw=true "Target Image")
![Mask](examples/unicorn-mask.png?raw=true "Target Mask")
![Output](examples/unicorn-qr.png?raw=true "Output Image")

![Target](examples/ctree.png?raw=true "Target Image")
![Mask](examples/ctree-mask.png?raw=true "Target Mask")
![Output](examples/ctree-qr.png?raw=true "Output Image")

![Target](examples/octopus.png?raw=true "Target Image")
![Mask](examples/octopus-mask.png?raw=true "Target Mask")
![Output](examples/octopus-qr.png?raw=true "Output Image")

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
python qrga.py --target crow.png --mask crow-mask.png --output crow-qr.png --data 'http://www.aaronvose.net' --gui
```

## Authors

* **Aaron Vose** - *Initial work* - [aaronvose.net](http://www.aaronvose.net)

## License

This project is licensed under the GPLv3 License - see the [LICENSE.md](LICENSE.md) file for details
