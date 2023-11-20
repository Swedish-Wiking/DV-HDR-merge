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

*Can be costumized to use `*.mp4` as HDR input as well but Matroska is the superior container.*<br>

**Output format**: `*.mkv`

## Examples
