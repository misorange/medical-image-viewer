# DICOM三断面ビューア 操作マニュアル

大学実験実習用のアプリです。Python **3.12** を使用してください。観点1～6の三断面表示と、観点7の第5回抽出済み肺領域の3Dボリュームレンダリングに対応します。診断には使用しないでください。

## 1. 必要な環境とインストール

Windows、macOS、Linuxのデスクトップ環境を想定しています。Python 3.12とTkinterが必要です。TkinterはPython標準添付のGUI機能で、pipでのインストールは不要です。ただしLinux等では別途OSの `python3-tk` パッケージが必要になる場合があります。

以下は、このフォルダをターミナルで開いて実行してください。

Windows（コマンドプロンプト）:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python --version
python -m pip install -r requirements.txt
python -m tkinter
python dicom_viewer.py
```

macOS / Linux:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install -r requirements.txt
python -m tkinter
python dicom_viewer.py
```

`python --version` が3.12系であることを確認してください。`python -m tkinter` で確認用ウィンドウが開いたら閉じてください。ソースのコンパイル作業は不要です。依存パッケージは `requirements.txt` にバージョンを固定しています。matplotlib等の間接依存はpipが解決します。

アプリの起動・DICOM読み込み・テスト実行では外部に接続しません。通常の `pip install` にはパッケージ取得用の接続が必要です。この提出物にはライブラリ本体は含めていません（指定のソースファイルのみ）。完全オフラインのPCで初回インストールする場合は、同じOS・CPU・Python 3.12の接続可能なPCで、間接依存も含むwheelを事前に用意してください。

```sh
python -m pip download --only-binary=:all: -r requirements.txt -d wheels
```

その `wheels` フォルダを対象PCへコピーして、次のコマンドでインストールします。

```sh
python -m pip install --no-index --find-links wheels -r requirements.txt
```

## 2. DICOMの読み込み

1. `python dicom_viewer.py` で起動します。未読み込み時は画面下部に使い方が表示され、スライダーは無効です。
2. 「ファイル」→「DICOMフォルダを開く…」でフォルダを指定します。直下の拡張子 `.dcm`（大文字も可）を読み込みます。サブフォルダは検索しません。
3. 複数シリーズが含まれる場合は、UIDと枚数を見て番号を入力してください。
4. 「単一DICOMファイルを開く…」では選択した1ファイルだけを読み込みます。そのファイルと同じフォルダの他のスライスは追加しません。単一スライスでも他の2断面は厚さ1画素の断面として表示します。

読み込み失敗時は理由をダイアログで知らせます。以前の読み込み済み画像は維持されます。個人情報を含む実データの管理は利用者が行ってください。

## 3. 三断面・十字線・スライダー

左からAxial（横断面）、Coronal（冠状断面）、Sagittal（矢状断面）を同時に表示します。画素間隔とスライス間隔をmm単位の縦横比へ反映します。

- Axialスライダー: z方向の位置を変更します。赤線は他の2画面上のAxial面位置です。
- Coronalスライダー: y方向の位置を変更します。青線は他の2画面上のCoronal面位置です。
- Sagittalスライダー: x方向の位置を変更します。緑線は他の2画面上のSagittal面位置です。
- 各画面の十字線の交点は、共通の3次元位置を表します。スライダーに連動して画像と線が移動します。
- WL: ウィンドウ中心値です。3画面共通で明るさの範囲を変更します。
- WW: ウィンドウ幅です。3画面共通でコントラストの範囲を変更します。1以上に制限しています。

スライス番号は0始まりです。画面下部に配列形状、間隔、患者座標での位置(z,y,x)、WL、WWを表示します。各画像の座標軸は画像先頭の画素中心からの距離(mm)です。

表示値は `clip((画素値 - (WL - WW/2)) / WW, 0, 1)` です。RescaleSlope/Interceptを適用した値を用い、MONOCHROME1では最後に白黒を反転します。初期WL/WWはDICOMの値（複数ある場合は先頭）を使い、なければ画素範囲から求めます。

配列は患者座標のz・y・xへ整列します。画面の上はAxialでは後側、Coronal/Sagittalでは頭側、右はAxial/Coronalでは左側、Sagittalでは後側です。一般の診断用ビューアと表示方向が異なる場合があります。

## 4. 対応範囲

単一フレームのモノクロDICOMシリーズに対応します。位置情報があればImagePositionPatientをスライス法線に射影して整列し、実際の位置差から間隔を求めます。なければInstanceNumberとSpacingBetweenSlices / SliceThicknessを用います。PixelSpacingがない場合は1mm、方向情報がない場合は標準Axial方向、位置情報がない場合は原点0と仮定します。その場合、物理位置は仮定値です。

患者座標軸に平行なAxial/Coronal/Sagittal取得画像は、方向の反転・軸の入れ替えを処理します。斜位、ガントリ傾斜による横ずれ、不均等間隔、重複位置、サイズ等が不一致のシリーズ、カラー、マルチフレームは対象外です。圧縮DICOMは追加デコーダが必要な場合があるため、追加ライブラリ不要の非圧縮DICOMを使用してください。

## 5. 肺領域の3D表示（観点7）

ファイルメニューの「第5回の肺領域を3D表示」を選ぶと別ウィンドウが開きます。同梱した `data/lungs.tif`（第5回の修正版、133枚）を使用します。単独起動は `python lung_viewer.py` です。

- 左ドラッグ：回転、ホイール：拡大縮小、中ボタンドラッグ：平行移動。
- 下部Opacityスライダー：不透明度を変更。
- `r` キー：視点をリセット。ウィンドウの×で終了。
- VTKのCPUレイキャストによる合成ボリュームレンダリングです。表面メッシュやMIPではありません。背景値0を透明にします。
- 画素間隔は同名のJSONの `spacing_zyx_mm` を読みます。同梱データは元CTの位置差・PixelSpacingから取得しています。
- 別データは `python lung_viewer.py path/to/lungs.tif`。8bitグレースケール連続TIFFに対応します。同名JSONがない場合は1×1×1の仮定値になるため、実寸比は保証しません。
- 同梱データは表示用8bitでありHUではありません。閾値ベースの抽出なので、気道の残存や肺の欠落がある可能性があります。
- OpenGL対応のデスクトップ環境が必要です。遠隔・仮想環境では描画できない場合があります。

## 6. 提出

フォルダ内のソース、requirements.txt、Markdown、dataをGitHubに置き、リポジトリURLを提出してください。元CTのDICOM個人情報や仮想環境は含めていません。インストール時にはネット接続が必要です。Python 3.12を指定して仮想環境を作成してください。
