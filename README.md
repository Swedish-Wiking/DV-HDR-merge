# DV_HDR_Merge
A script to batch combine HDR media with Dolby Vison media for a hybrid file that uses Dolby Vision but with fallback to HDR.
The script has a bulit in frame compare tool that makes syncing the different files very easy. 
The script matches the files by comparing frame count because Dolby Vision RPU-files are base on frames, not on time.

## Dependencies
**[FFmpeg](https://github.com/FFmpeg/FFmpeg)** needs to be installed to path<br>
**[requirements.txt](https://github.com/Swedish-Wiking/DV_HDR_Merge/blob/main/requirements.txt)** needs to be installed with pip
### Accompanying dependencies:
**[quietvoid/dovi_tool](https://github.com/quietvoid/dovi_tool)** Thanks for making this possible!<br>
**[mkvmerge](https://mkvtoolnix.download/doc/mkvmerge.html)**<br>
**[mkvextract](https://mkvtoolnix.download/doc/mkvextract.html)**<br>

## Usage
```properties
DV_HDR_Merge.py [Input files/folders]
```
Optional commands: `--help`, `-logL`, `-maxdif`

```console
DV_HDR_Merge.py -logL debug -maxdif 100 HDR_movie.mkv DV_movie.mp4 HDR_movie2.mkv DV_movie2.mkv ./DV_movie_folder ./HDR_movie_folder
```
**Valid input formats**: <br>
HDR media: `*.mkv`<br>
Dolby Vision media: `*.mkv`, `*.mp4`<br>

*Can be customized to use `*.mp4` as HDR input as well but Matroska is the superior container.*<br>

**Output format**: `*.mkv`

### Explanations

**Shift frames**:<br>
A negative amount means that frames will be removed in the beginning and a positive means that the first frame will be duplicated to add enough frame.
Any excess frame on the end will be cut off

**General**:<br>
If frame dimensions do not match the script will automagically correct for it.

### Example of code running
![Command Promt running script](/EXAMPLES/RUNNING.png)

## Frame Compare Tool

![Application window](/EXAMPLES/APPLICATION.png)

1. Opens the active image in your default photo application for easier inspection
2. Switches between a 50/50 blend of the two compared images or a greyscale difference 
3. Set the frame to refrence in the HDR media file, press `Enter` to apply. (Total amount of frames in media is shown in label) 
4. Set how may frames to shift Dolby Vision layer with, press `Enter` to apply.
5. Closes window and sends inputed frame-shift to be used when combining the two media.<br>
(Closing the window will do the same as the `Done` button)

Always compare multiple refrence frames in case of missing or extra frames in some of the materials used.

### Example images

Both senarios are using frame 30000 as the HDR refrence frame.

#### Unsynced images
<p float="left">
  <img src="/EXAMPLES/UNSYNCED.PNG" width="49%" height="auto">
  <img src="/EXAMPLES/UNSYNCED_DIF.PNG" width="49%" height="auto">
</p>
*No frame shift have been added and the result is blurry edges and sometimes even different scenes. The difference images shows a lot of anomalies when pixels don't cancel each other out.*

#### Synced images
<p float="left">
  <img src="/EXAMPLES/SYNCED.PNG" width="49%" height="auto">
  <img src="/EXAMPLES/SYNCED_DIF.PNG" width="49%" height="auto">
</p>
*When Dolby Vison layer is shifted with -3 no blurry edges can be seen on the blend iamge and on the difference image no anomalies can be found. (Sometimes you can get a fades silhouette as in this case because the luminance levels could not be correctly matched when trying to tonemap the thumbnails taken from the media)*

## Known bugs...

- When extracting, modifying and injecting the RPU file no live progress is shown because of a problem catching output from *dovi_tool*
