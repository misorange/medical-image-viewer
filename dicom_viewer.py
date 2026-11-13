"""Python 3.12用・実習用DICOM三断面ビューア（診断用途ではない）。"""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pydicom


@dataclass
class Volume:
    """配列の順序は患者座標の z, y, x（頭側、後側、左側が正）。"""
    data: np.ndarray
    spacing: tuple[float, float, float]
    origin: tuple[float, float, float]
    wl: float
    ww: float
    inverted: bool = False


def discover_series(path):
    """直下の.dcmをシリーズUID単位でまとめる。単一ファイルも受け付ける。"""
    path = Path(path)
    files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == '.dcm') if path.is_dir() else [path]
    if not files:
        raise ValueError('選択先に.dcmファイルがありません。')
    groups = {}
    for file in files:
        ds = pydicom.dcmread(file, stop_before_pixels=True)
        uid = str(getattr(ds, 'SeriesInstanceUID', 'UIDなし'))
        groups.setdefault(uid, []).append(file)
    return groups


def load_volume(path, series_uid=None):
    """位置またはInstanceNumberで整列し、RescaleSlope/Interceptを適用する。"""
    groups = discover_series(path)
    if series_uid is None:
        if len(groups) != 1:
            raise ValueError('複数シリーズがあります。読み込むシリーズを選択してください。')
        series_uid = next(iter(groups))
    datasets = [pydicom.dcmread(p) for p in groups[series_uid]]
    first = datasets[0]
    for ds in datasets:
        if int(getattr(ds, 'NumberOfFrames', 1)) != 1 or int(getattr(ds, 'SamplesPerPixel', 1)) != 1:
            raise ValueError('単一フレームのモノクロDICOMのみ対応しています。')
        if ds.PhotometricInterpretation not in ('MONOCHROME1', 'MONOCHROME2'):
            raise ValueError('モノクロ画像のみ対応しています。')
    orientation = np.asarray(getattr(first, 'ImageOrientationPatient', [1, 0, 0, 0, 1, 0]), dtype=float)
    # 軸に平行な画像は取得方向を問わず患者座標へ並べ替える。
    col, row = orientation[:3], orientation[3:]
    normal = np.cross(col, row)
    vectors = np.array([normal, row, col])
    axes = np.argmax(np.abs(vectors), axis=1)
    if len(set(axes)) != 3 or not np.allclose(np.abs(vectors), np.eye(3)[axes], atol=1e-4):
        raise ValueError('斜位画像は未対応です。患者座標軸に平行なシリーズを選択してください。')
    pixel_spacing = np.asarray(getattr(first, 'PixelSpacing', [1, 1]), dtype=float)
    if pixel_spacing.shape != (2,) or np.any(pixel_spacing <= 0):
        raise ValueError('PixelSpacingが不正です。')
    for ds in datasets:
        if (ds.Rows, ds.Columns) != (first.Rows, first.Columns) or not np.allclose(getattr(ds, 'ImageOrientationPatient', orientation), orientation) or not np.allclose(getattr(ds, 'PixelSpacing', pixel_spacing), pixel_spacing):
            raise ValueError('画像サイズ・方向・画素間隔がシリーズ内で一致しません。')
    positioned = [hasattr(ds, 'ImagePositionPatient') for ds in datasets]
    if any(positioned) and not all(positioned):
        raise ValueError('画像位置情報が一部のスライスで欠落しています。')
    thickness = abs(float(getattr(first, 'SpacingBetweenSlices', getattr(first, 'SliceThickness', 1))))
    if all(positioned):
        datasets.sort(key=lambda ds: float(np.dot(ds.ImagePositionPatient, normal)))
        positions = np.array([ds.ImagePositionPatient for ds in datasets], dtype=float)
        if len(datasets) > 1:
            gaps = np.diff(positions @ normal)
            thickness = float(np.median(gaps))
            if thickness <= 0 or not np.allclose(gaps, thickness, rtol=.01, atol=.01):
                raise ValueError('重複位置または不均等なスライス間隔があります。')
            if not np.allclose(np.diff(positions, axis=0), thickness * normal, atol=.01):
                raise ValueError('スライス間に横方向のずれがあります。')
        origin = positions[0].copy()
    else:
        if len(datasets) > 1:
            numbers = [int(ds.InstanceNumber) for ds in datasets]
            if len(set(numbers)) != len(numbers):
                raise ValueError('InstanceNumberが重複しています。')
            datasets.sort(key=lambda ds: int(ds.InstanceNumber))
        origin = np.zeros(3)
    if not np.isfinite(thickness) or thickness <= 0:
        raise ValueError('スライス間隔が不正です。')
    data = np.stack([ds.pixel_array.astype(np.float32) * float(getattr(ds, 'RescaleSlope', 1)) + float(getattr(ds, 'RescaleIntercept', 0)) for ds in datasets])
    spacing = np.array([thickness, *pixel_spacing])
    # 配列の各軸を正方向にそろえ、最後にz,y,xへ転置する。
    for axis, patient_axis in enumerate(axes):
        if vectors[axis, patient_axis] < 0:
            origin[patient_axis] -= spacing[axis] * (data.shape[axis] - 1)
            data = np.flip(data, axis=axis)
    order = [int(np.where(axes == a)[0][0]) for a in (2, 1, 0)]
    data = np.transpose(data, order)
    def scalar(value):
        return float(value[0] if isinstance(value, (list, tuple, pydicom.multival.MultiValue)) else value)
    wl = scalar(first.WindowCenter) if hasattr(first, 'WindowCenter') else float((data.min() + data.max()) / 2)
    ww = scalar(first.WindowWidth) if hasattr(first, 'WindowWidth') else max(float(np.ptp(data)), 1)
    return Volume(data, tuple(spacing[order]), tuple(origin[::-1]), wl, max(ww, 1), first.PhotometricInterpretation == 'MONOCHROME1')


def window_image(pixels, wl, ww):
    """課題指定の式で0～1に正規化する。"""
    if not np.isfinite(wl) or not np.isfinite(ww) or ww <= 0:
        raise ValueError('WWは正の数にしてください。')
    return np.clip((np.asarray(pixels, dtype=float) - (wl - ww / 2)) / ww, 0, 1)


def extract_slice(volume, plane, indices):
    """断面、表示画素間隔、十字線の列/行位置を返す。"""
    z, y, x = indices
    dz, dy, dx = volume.spacing
    if plane == 'Axial':
        return volume.data[z, :, :], (dy, dx), (x, y)
    if plane == 'Coronal':
        return volume.data[:, y, :], (dz, dx), (x, z)
    if plane == 'Sagittal':
        return volume.data[:, :, x], (dz, dy), (y, z)
    raise ValueError('不明な断面です。')


def draw_slice(ax, volume, plane, indices, wl, ww):
    """GUIとPNG出力で共通の描画処理。座標はmm。"""
    pixels, (vertical, horizontal), (cx, cy) = extract_slice(volume, plane, indices)
    shown = window_image(pixels, wl, ww)
    if volume.inverted:
        shown = 1 - shown
    h, w = pixels.shape
    ax.clear()
    ax.set_axis_on()
    ax.imshow(shown, cmap='gray', vmin=0, vmax=1, origin='lower', extent=(-horizontal/2, (w-.5)*horizontal, -vertical/2, (h-.5)*vertical), aspect='equal', interpolation='nearest')
    # 線色はそれぞれの断面の位置スライダーと対応する。
    colors = {'Axial': ('#4ade80', '#60a5fa'), 'Coronal': ('#4ade80', '#f87171'), 'Sagittal': ('#60a5fa', '#f87171')}
    a, b = colors[plane]
    ax.axvline(cx * horizontal, color=a, linewidth=.8)
    ax.axhline(cy * vertical, color=b, linewidth=.8)
    ax.set_title(plane)
    ax.set_xlabel('mm')
    ax.set_ylabel('mm')


def main():
    """TkinterはGUI起動時だけ読み込み、Aggからも関数を利用できる。"""
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    root = tk.Tk()
    root.title('DICOM 三断面ビューア — Python 3.12')
    root.geometry('1200x780')
    root.minsize(800,600)
    root.rowconfigure(0,weight=1)
    root.columnconfigure(0,weight=1)
    volume = None
    figure = Figure(figsize=(12, 5), constrained_layout=True)
    axes = figure.subplots(1, 3)
    canvas = FigureCanvasTkAgg(figure, master=root)
    canvas.get_tk_widget().grid(row=0,column=0,sticky='nsew')
    status = tk.StringVar(value='ファイルメニューからDICOMフォルダ、または単一.dcmファイルを選択してください。')
    tk.Label(root, textvariable=status, wraplength=780).grid(row=1,column=0,sticky='ew')
    controls = tk.Frame(root)
    controls.grid(row=2,column=0,sticky='ew')
    sliders = {}
    planes = ('Axial', 'Coronal', 'Sagittal')

    def refresh(*_):
        if volume is None:
            return
        indices = [int(sliders[p].get()) for p in planes]
        wl, ww = sliders['WL'].get(), sliders['WW'].get()
        for ax, plane in zip(axes, planes):
            draw_slice(ax, volume, plane, indices, wl, ww)
        position = [volume.origin[i] + indices[i] * volume.spacing[i] for i in range(3)]
        status.set(f'形状(z,y,x): {volume.data.shape} / 間隔(mm): {tuple(round(float(v), 3) for v in volume.spacing)} / 位置(z,y,x mm): {tuple(round(float(v), 2) for v in position)} / WL={wl:.1f}, WW={ww:.1f}')
        canvas.draw_idle()

    for name, color in zip((*planes, 'WL', 'WW'), ('#f87171', '#60a5fa', '#4ade80', 'black', 'black')):
        frame = tk.Frame(controls)
        frame.pack(fill='x')
        tk.Label(frame, text=name, width=10, fg=color).pack(side='left')
        slider = tk.Scale(frame, from_=0, to=1, orient='horizontal', command=refresh, state='disabled')
        slider.pack(side='left', fill='x', expand=True)
        sliders[name] = slider

    def open_data(folder):
        nonlocal volume
        path = filedialog.askdirectory(title='DICOMフォルダを選択') if folder else filedialog.askopenfilename(title='単一DICOMを選択', filetypes=[('DICOM', '*.dcm'), ('すべて', '*')])
        if not path:
            return
        try:
            groups = discover_series(path)
            uid = next(iter(groups))
            if len(groups) > 1:
                keys = list(groups)
                description = '\n'.join(f'{i+1}: {key} ({len(groups[key])}枚)' for i, key in enumerate(keys))
                choice = simpledialog.askinteger('シリーズ選択', description + '\n読み込む番号:', minvalue=1, maxvalue=len(keys), parent=root)
                if choice is None:
                    return
                uid = keys[choice - 1]
            loaded = load_volume(path, uid)
            volume = None  # 設定途中のコールバックを抑止する。
            for plane, size in zip(planes, loaded.data.shape):
                sliders[plane].configure(state='normal', from_=0, to=max(size-1, 0), resolution=1)
                sliders[plane].set(size // 2)
            lo, hi = float(loaded.data.min()), float(loaded.data.max())
            span = max(hi-lo, loaded.ww, 1)
            sliders['WL'].configure(state='normal', from_=min(lo-span, loaded.wl), to=max(hi+span, loaded.wl), resolution=.1)
            sliders['WW'].configure(state='normal', from_=1, to=max(2*span, loaded.ww), resolution=.1)
            sliders['WL'].set(loaded.wl)
            sliders['WW'].set(loaded.ww)
            volume = loaded
            refresh()
        except Exception as exc:
            messagebox.showerror('読み込みエラー', f'DICOMを読み込めませんでした。\n{exc}', parent=root)

    def open_lungs():
        import subprocess, sys
        subprocess.Popen([sys.executable,str(Path(__file__).with_name('lung_viewer.py'))])

    menu = tk.Menu(root)
    file_menu = tk.Menu(menu, tearoff=False)
    file_menu.add_command(label='DICOMフォルダを開く…', command=lambda: open_data(True))
    file_menu.add_command(label='単一DICOMファイルを開く…', command=lambda: open_data(False))
    file_menu.add_command(label='第5回の肺領域を3D表示', command=open_lungs)
    file_menu.add_separator()
    file_menu.add_command(label='終了', command=root.destroy)
    menu.add_cascade(label='ファイル', menu=file_menu)
    root.configure(menu=menu)
    for ax, plane in zip(axes, planes):
        ax.set_title(plane)
        ax.text(.5, .5, 'File menu: Open DICOM', ha='center', va='center', transform=ax.transAxes)
        ax.set_axis_off()
    canvas.draw_idle()
    root.mainloop()


if __name__ == '__main__':
    main()
