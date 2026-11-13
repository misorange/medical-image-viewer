# Medical Image Viewer

Python 3.12製の医用画像ビューアです。DICOMの三断面表示、スライス位置とWL/WWの調整、肺領域の3Dボリュームレンダリングに対応します。

導入と操作方法は [MANUAL.md](MANUAL.md)、検証内容は [VERIFICATION.md](VERIFICATION.md) を参照してください。

```sh
python -m pip install -r requirements.txt
python dicom_viewer.py
```

第5回の抽出済み肺データを同梱しています。「ファイル → 第5回の肺領域を3D表示」から表示できます。三断面表示用のDICOMは別途選択してください。

実習用です。診断用途には使用しません。
