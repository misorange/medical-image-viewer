"""Lung TIFF volume rendering, Python 3.12. Not for diagnosis."""
from pathlib import Path
import argparse,json
import numpy as np
from PIL import Image, ImageSequence

def load_lungs(path):
    with Image.open(path) as im:
        frames=[]
        for f in ImageSequence.Iterator(im):
            a=np.asarray(f)
            if a.ndim!=2 or a.dtype!=np.uint8:
                raise ValueError('8-bit grayscale multi-page TIFF required')
            frames.append(a.copy())
    if len(frames)<2: raise ValueError('Multi-page TIFF required')
    return np.stack(frames)

def make_scene(data, spacing):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk
    image=vtk.vtkImageData();image.SetDimensions(*data.shape[::-1]);image.SetSpacing(*spacing[::-1])
    image.GetPointData().SetScalars(numpy_to_vtk(data.ravel(),deep=True,array_type=vtk.VTK_UNSIGNED_CHAR))
    mapper=vtk.vtkFixedPointVolumeRayCastMapper();mapper.SetInputData(image);mapper.SetBlendModeToComposite()
    mapper.SetSampleDistance(min(spacing)*.8)
    color=vtk.vtkColorTransferFunction()
    color.AddRGBPoint(0,0,0,0);color.AddRGBPoint(30,.85,.65,.55);color.AddRGBPoint(120,.9,.65,.55);color.AddRGBPoint(255,1,.95,.9)
    alpha=vtk.vtkPiecewiseFunction()
    prop=vtk.vtkVolumeProperty();prop.SetColor(color);prop.SetScalarOpacity(alpha);prop.SetInterpolationTypeToLinear();prop.ShadeOn();prop.SetAmbient(.65);prop.SetDiffuse(.35)
    prop.SetScalarOpacityUnitDistance(min(spacing))
    vol=vtk.vtkVolume();vol.SetMapper(mapper);vol.SetProperty(prop)
    ren=vtk.vtkRenderer();ren.SetBackground(.06,.08,.12);ren.AddVolume(vol)
    win=vtk.vtkRenderWindow();win.SetWindowName('Lung volume rendering');win.SetSize(1000,800);win.AddRenderer(ren)
    center=image.GetCenter();camera=ren.GetActiveCamera();camera.SetFocalPoint(*center);camera.SetPosition(center[0],center[1]-1000,center[2]);camera.SetViewUp(0,0,1);ren.ResetCamera();camera.Azimuth(20);camera.Elevation(10);camera.Zoom(1.3);ren.ResetCameraClippingRange()
    def opacity(value):
        alpha.RemoveAllPoints();alpha.AddPoint(0,0);alpha.AddPoint(1,0)
        alpha.AddPoint(30,.04*value);alpha.AddPoint(120,.25*value);alpha.AddPoint(255,.6*value)
    opacity(.5)
    return win,ren,opacity

def main():
    import vtk
    parser=argparse.ArgumentParser();parser.add_argument('path',nargs='?',default=str(Path(__file__).parent/'data/lungs.tif'));parser.add_argument('--snapshot');args=parser.parse_args()
    path=Path(args.path);data=load_lungs(path)
    sidecar=path.with_suffix('.json')
    spacing=json.loads(sidecar.read_text(encoding='utf-8'))['spacing_zyx_mm'] if sidecar.exists() else [1.,1.,1.]
    if len(spacing)!=3 or not np.all(np.isfinite(spacing)) or min(spacing)<=0:raise ValueError('Invalid spacing')
    win,ren,opacity=make_scene(data,spacing)
    if args.snapshot:
        win.SetOffScreenRendering(1);win.Render();f=vtk.vtkWindowToImageFilter();f.SetInput(win);f.Update();w=vtk.vtkPNGWriter();w.SetFileName(args.snapshot);w.SetInputConnection(f.GetOutputPort());w.Write();win.Finalize();return
    iren=vtk.vtkRenderWindowInteractor();iren.SetRenderWindow(win);iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    rep=vtk.vtkSliderRepresentation2D();rep.SetMinimumValue(.05);rep.SetMaximumValue(1.);rep.SetValue(.5);rep.SetTitleText('Opacity')
    rep.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay();rep.GetPoint1Coordinate().SetValue(.2,.08);rep.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay();rep.GetPoint2Coordinate().SetValue(.8,.08)
    slider=vtk.vtkSliderWidget();slider.SetInteractor(iren);slider.SetRepresentation(rep);slider.AddObserver('InteractionEvent',lambda o,e:(opacity(o.GetRepresentation().GetValue()),win.Render()))
    iren.Initialize();slider.EnabledOn();win.Render();iren.Start()
if __name__=='__main__':main()

