from pathlib import Path
import sys
import numpy as np
from dicom_viewer import Volume,extract_slice,window_image
from lung_viewer import load_lungs
v=Volume(np.arange(24).reshape(2,3,4),(2,1,1),(0,0,0),12,24)
assert extract_slice(v,'Axial',(1,1,2))[0].shape==(3,4)
assert extract_slice(v,'Coronal',(1,1,2))[2]==(2,1)
assert extract_slice(v,'Sagittal',(1,1,2))[2]==(1,1)
assert np.allclose(window_image([-1,0,1],0,2),[0,.5,1])
a=load_lungs(Path(__file__).parent/'data/lungs.tif');assert a.shape==(133,512,512);assert not a[17].any()
print('PASS: slices, crosshair coordinates, window, bundled lung data')
