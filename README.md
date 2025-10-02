# DV-HDR-merge

A script to batch combine HDR media with Dolby Vision media for a hybrid file that uses Dolby Vision but with fallback to HDR.
The script has a built in frame compare tool that makes syncing the different files very easy.
The script matches the files by comparing frame count because Dolby Vision RPU-files are based on frames, not on time.

## Dependencies

The following dependencies must either be installed to PATH or added to a folder called `bin` in the main directory:

**[FFmpeg](https://github.com/FFmpeg/FFmpeg)**
**[quietvoid/dovi_tool](https://github.com/quietvoid/dovi_tool)**\
**[mkvmerge](https://mkvtoolnix.download/doc/mkvmerge.html)**\
**[mkvextract](https://mkvtoolnix.download/doc/mkvextract.html)**

Python requirements that needs to be installed:
**[requirements.txt](https://github.com/Swedish-Wiking/DV_HDR_Merge/blob/main/requirements.txt)**

## Usage

```properties
DV_HDR_Merge.py [Input files/folders]
```

Optional commands: `--help`, `-logL`, `-maxdif`

```bash
DV_HDR_Merge.py -logL debug -maxdif 100 HDR_movie.mkv DV_movie.mp4 HDR_movie2.mkv DV_movie2.mkv ./DV_movie_folder ./HDR_movie_folder
```

**Valid input formats**:\
HDR media: `*.mkv`\
Dolby Vision media: `*.mkv`, `*.mp4`\

*Can be customized to use `*.mp4` as HDR input as well but Matroska is the superior container.*\

**Output format**: `*.mkv`

### Explanations

**Shift frames**:\
A negative amount means that frames will be removed in the beginning and a positive means that the first frame will be duplicated to add enough frame.
Any excess frame on the end will be cut off

**General**:\
If frame dimensions do not match the script will automagically correct for it.

### Example of code running

![Command Prompt running script](/EXAMPLES/RUNNING.png)

## Frame Compare Tool

![Application window](/EXAMPLES/APPLICATION.png)

1. Opens the active image in your default photo application for easier inspection
2. Switches between a 50/50 blend of the two compared images or a grey-scale difference
3. Set the frame to reference in the HDR media file, press `Enter` to apply. (Total amount of frames in media is shown in label)
4. Set how may frames to shift Dolby Vision layer with, press `Enter` to apply.
5. Closes window and sends inputted frame-shift to be used when combining the two media.\
(Closing the window will do the same as the `Done` button)

Always compare multiple reference frames in case of missing or extra frames in some of the materials used.

### Example images

Both scenarios are using frame 30000 as the HDR reference frame.

#### Unsynced images

Blended 50/50                           | Difference
:--------------------------------------:|:----------------------------------------------:
![Synced Normal](/EXAMPLES/UNSYNCED.PNG)  |  ![Synced Difference](/EXAMPLES/UNSYNCED_DIF.PNG)

No frame shift have been added and the result is blurry edges and sometimes even different scenes. The difference images shows a lot of anomalies when pixels don't cancel each other out.

#### Synced images

Blended 50/50                           | Difference
:--------------------------------------:|:----------------------------------------------:
![Synced Normal](/EXAMPLES/SYNCED.PNG)  |  ![Synced Difference](/EXAMPLES/SYNCED_DIF.PNG)

When Dolby Vision layer is shifted with -3 frames in this cae, no blurry edges can be seen on the blend image and on the difference image no anomalies can be found. (Sometimes you can get a faded silhouette as in this case because the luminance levels could not be correctly matched when trying to tonemap the thumbnails taken from the media)
