import argparse
import json
import logging
import re
import subprocess
import tkinter
import tkinter.filedialog
import tkinter.font
from pathlib import Path
from shutil import rmtree, which

import questionary
from PIL import Image, ImageChops, ImageTk
from pymediainfo import MediaInfo
from questionary import ValidationError, Validator
from rich.progress import (BarColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn, TimeElapsedColumn,
                           TimeRemainingColumn)
from winpty import PtyProcess

parser = argparse.ArgumentParser(
    prog="Dolby Vision + HDR", 
    description="A program to combine HDR videos with Dolby Vison videos for a Dolby Vison file with HDR fallback", 
    epilog="Report bugs to Swedish-Wiking@GitHub"
)
parser.add_argument(
    "files", 
    nargs="*", 
    help="Paths of files and folders", 
    type=Path
    )
parser.add_argument(
    "-logs", 
    dest="logs", 
    choices=["DEBUG", "INFO", "ERROR"], 
    help="Set verbosity level"
)
parser.add_argument(
    "-maxdif", 
    dest="maxdif", 
    type=int, 
    help="Set maxed allowed frames to differ between videos"
)
parser.add_argument(
    "--temp-folder",
    dest="tempFolder",
    type=Path,
    help="A folder to which to save the converted ringtones",
)
args = parser.parse_args()

logging.basicConfig(format="%(levelname)s:\t%(message)s", level=logging.INFO)
logging.basicConfig(level=args.logs)

def get_exe(name: str) -> Path:
    _bins = Path(__file__).parent.resolve().joinpath("bin")
    if which(name) is not None: return Path(which(name)) # type: ignore
    elif _bins.joinpath(name).exists(): return _bins.joinpath(name)
    raise FileExistsError(f"The executable {name} does not exist on PATH")

def collect_files(list_of_paths: list[Path], filter: list[str] = [".mp4", ".mkv"]) -> list[Path]:
    files = list()
    for f in list_of_paths:
        if f.is_file() and f.suffix in filter: files.append(f)
        elif f.is_dir(): [files.append(p) for p in f.rglob("*") if p.suffix in filter]
    return files

FFMPEG = get_exe("ffmpeg")
FFPROBE = get_exe("ffprobe")
MKVMERGE = get_exe("mkvmerge")
MKVEXTRACT = get_exe("mkvextract")
DOVI_TOOL = get_exe("dovi_tool.exe")

temp_workdir = (
    args.tempFolder
    if args.tempFolder
    else Path(__file__).parent.resolve().joinpath("temp")
)

class NumberValidator(Validator):
    def validate(self, document):
        ok = re.match(
            r"^\d+$",
            document.text,
        )
        if not ok:
            raise ValidationError(
                message="Please enter a valid number",
                cursor_position=len(document.text),
            )

class ColorMerger():

    def __init__(self, files:list[Path]) -> None:
        self.files = self._tkAskForFiles() if not files else files
        if len(self.files) <= 1:
            logging.error("Not enough files were choosen!")
            exit(1)
        self.metadata = list(self._analyzeFiles())
        self.printMedia()
        self._checkColors()
        self.matchedFiles = self._matchFiles()

    def _tkAskForFiles(self) -> list[Path]:
        filetypes = (
            ("Video files", ".mkv .mp4"), 
            ("Matroska files", ".mkv"), 
            ("MPEG-4 files", ".mp4"), 
            ("All files", "*.*")
        )
        files = tkinter.filedialog.askopenfilenames(
            title="Select files",
            filetypes=filetypes
        )
        return [Path(file) for file in files]

    def _analyzeFiles(self):
        for file in sorted(self.files):
            logging.info(f"Analyzing {file.name}...")
            probe_cmd = [
                FFPROBE,
                "-hide_banner",
                "-loglevel", "fatal",
                "-show_error",
                "-show_streams",
                "-select_streams", "v:0",
                "-show_private_data",
                "-print_format", "json",
                file
            ]

            data = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if data.returncode != 0:
                logging.warning(f"File could not be analyzed: {data.stderr}")
                break
            
            parsed_data = self.parseMetadata(data.stdout.decode("utf-8"), file)
            logging.info("Sucessfully analyzed file!")
            yield {"name": file.name, "path": file} | parsed_data
    
    @staticmethod
    def parseMetadata(data, file):
        json_data = json.loads(data)
        logging.debug(json_data)
        json_data = json_data["streams"][0]
        width = int(json_data["width"])
        height = int(json_data["height"])
        fps = json_data["avg_frame_rate"].split("/")
        fps = int(fps[0]) / int(fps[1])
        frameCount = 0
        colorProfile = "None"

        try: 
            frameCount = int(json_data["tags"]["NUMBER_OF_FRAMES"])
        except:
            try: 
                frameCount = int(json_data["tags"]["NUMBER_OF_FRAMES-eng"])
            except:
                try: 
                    frameCount = int(json_data["nb_frames"])
                except:
                    logging.warning("Framerate was not found in ffprobe data, using MediaInfo")
                    logging.warning("Analysis may take longer")
                    media_info = MediaInfo.parse(file)
                    for track in media_info.tracks: 
                        if track.track_type == "Video": 
                            frameCount = int(track.frame_count)
        
        try: 
            if json_data["side_data_list"][0]["rpu_present_flag"] == 1: 
                try:
                    if json_data["color_transfer"] == "smpte2084": 
                        colorProfile = "HDR+DV"
                except: 
                    colorProfile = "DV"
        except:
            try: 
                if json_data["color_transfer"] == "smpte2084": 
                    colorProfile = "HDR"
            except: 
                colorProfile = "None"

            
        
        return {"frameCount": frameCount, "colorProfile": colorProfile, "pxWidth": width, "pxHeight": height, "frameRate": fps}

    def _checkColors(self):
        cProfile = {d["colorProfile"] for d in self.metadata}
        if ("DV" not in cProfile and "HDR+DV" not in cProfile) or not "HDR" in cProfile:
            logging.error("Not enough files with HDR or DV layers")
            exit(1)

    def printMedia(self) -> None:

        def printInfo(profile:str) -> None:
            logging.info(f"{profile} Media:")
            for media in filter(lambda d: d["colorProfile"] == profile, self.metadata):
                logging.info(f"{media["name"]}:\n\tFrameCount: {media["frameCount"]}\n\tWidth: {media["pxWidth"]}\n\tHeight: {media["pxHeight"]}\n\tFrameRate: {media["frameRate"]}")

        for profile in {d["colorProfile"] for d in self.metadata}:
            printInfo(profile)

    @staticmethod
    def delayFrames(hdr, dv, hybrid:bool):
        logging.warning("Dolby Vision layer probably needs to be delayed")
        isManual = questionary.confirm("Do you want to input value to shift frames with?", default=False).ask()
        if isManual:
            delayed_frames = int(
                questionary.text(
                    "Input frames to shift Dolby Vision layer with:", 
                    qmark = "", 
                    validate = NumberValidator
                ).ask()
            )
        else:
            comparer = CompareWindow(hdr, dv, hybrid)
            delayed_frames = comparer.shifted_frames
        logging.info(f"Dolby Vision layer is shifted by {delayed_frames} frames")
        return delayed_frames

    def _matchFiles(self):
        matched_files = list()
        HDRs = [media for media in self.metadata if media["colorProfile"] == "HDR"]
        logging.debug(HDRs)
        DVs = [media for media in self.metadata if media["colorProfile"] in ["DV", "HDR+DV"]]
        logging.debug(DVs)
        if args.maxdif != None: 
            maxDif = int(args.maxdif)
        else: 
            maxDif = int(
                questionary.text(
                    "Input max allowed differance in frames:", 
                    qmark = "", 
                    validate = NumberValidator
                ).ask()
            )
        
        logging.info("Matching files...")
        for hdr_file in HDRs:
            miss = 0
            logging.info(f"Trying to match: {hdr_file["name"]}")
            for dv_file in DVs:
                hybrid = True if dv_file["colorProfile"] == "HDR+DV" else False
                absDif = abs(hdr_file["frameCount"] - dv_file["frameCount"])
                if absDif == 0:
                    logging.info(f"Perfect match found with: {dv_file["name"]}")
                    isAutomatic = questionary.confirm("Want to frame match anyways", default=False).ask()
                    if isAutomatic: frames_to_delay = self.delayFrames(hdr_file, dv_file, hybrid)
                    else: frames_to_delay = 0
                    match = {"HDR_FILE": hdr_file, "DV_FILE": dv_file, "framesToDelay": frames_to_delay}
                    matched_files.append(match)
                    break
                elif(absDif <= maxDif):
                    logging.info(f"Match found but with a difference of: {absDif} frames, file matched with: {dv_file["name"]}")
                    isMatch = questionary.confirm("Is it a match", default=False).ask()
                    if isMatch:
                        frames_to_delay = self.delayFrames(hdr_file, dv_file, hybrid)
                        match = {"HDR_FILE": hdr_file, "DV_FILE": dv_file, "framesToDelay": frames_to_delay}
                        matched_files.append(match)
                    else: logging.info("Trying another...")
                else: miss += 1
                if miss == len(DVs): 
                    logging.warning(f"No match found for: {hdr_file["name"]}")
        
        logging.info("Matching process completeded")
        logging.debug(matched_files)
        return matched_files

    def _main(self, file_pair:dict):
        self.mkTemp()
        rpu_json = temp_workdir.joinpath("RPU.json")
        rpu = temp_workdir.joinpath("RPU.bin")
        rpu_edited = temp_workdir.joinpath("RPU_EDITED.bin")
        hdr_hevc = temp_workdir.joinpath("HDR.hevc")
        dv_hevc = temp_workdir.joinpath("DV.hevc")
        hdr_dv_hevc = temp_workdir.joinpath("HDR_DV.hevc")

        isDVmp4 = (file_pair["DV_FILE"]["path"] == ".mp4")
        
        delay_frames = file_pair["framesToDelay"]
        if delay_frames < 0:
            remove_frames = "0-" + str(abs(delay_frames)-1)
            delay_frames = 0
        else: remove_frames = ""

        crop = False
        crop_amount = 0
        if (file_pair["HDR_FILE"]["pxHeight"] == file_pair["DV_FILE"]["pxHeight"]): 
            logging.debug("No crop needed for RPU-file")
        elif (int(file_pair["HDR_FILE"]["pxHeight"]) > int(file_pair["DV_FILE"]["pxHeight"])):
            logging.debug("Adding letterboxing to RPU-file to match with target file")
            crop_amount = int((int(file_pair["HDR_FILE"]["pxHeight"]) - int(file_pair["DV_FILE"]["pxHeight"]))/2)
        elif (int(file_pair["HDR_FILE"]["pxHeight"]) < int(file_pair["DV_FILE"]["pxHeight"])):
            logging.debug("Croping needed for RPU-file")
            crop = True
            
        json_data = {
            "active_area": {
                "crop": crop,
                "presets": [{
                        "id": 0,
                        "left": 0,
                        "right": 0,
                        "top": crop_amount,
                        "bottom": crop_amount
                    }]},
            "remove": [
                remove_frames
            ],
            "duplicate": [{
                    "source": 0,
                    "offset": 0,
                    "length": delay_frames
                }]}
        
        with open(rpu_json, "w") as outfile: outfile.write(json.dumps(json_data, indent=4))

        cmdExtractHDRMKV = [
            MKVEXTRACT, 
            "tracks", 
            file_pair["HDR_FILE"]["path"], 
            "0:" + str(hdr_hevc), 
            "--gui-mode"] #1
        
        cmdExtractDVMKV = [
            MKVEXTRACT, 
            "tracks", 
            file_pair["DV_FILE"]["path"], 
            "0:" + str(dv_hevc), 
            "--gui-mode"] #2
        
        cmdExtractDV = [
            "ffmpeg", 
            "-loglevel", "error", 
            "-hide_banner", 
            "-progress", "-",
            "-nostats",
            "-analyzeduration", "6000M",
            "-probesize", "2147M", 
            "-y", 
            "-i", file_pair["DV_FILE"]["path"], 
            "-an", "-c:v", 
            "copy", 
            "-f", "hevc", 
            dv_hevc] #2
        
        cmdExtractRPU = [
            DOVI_TOOL, 
            "extract-rpu", 
            dv_hevc, 
            "-o", rpu] #3
        
        cmdRPUEdit = [
            DOVI_TOOL, 
            "editor",
            "-i", rpu, 
            "-j", rpu_json, 
            "-o", rpu_edited] #4
        
        cmdRPUInject = [
            DOVI_TOOL, 
            "inject-rpu",
            "-i", hdr_hevc, 
            "--rpu-in", rpu_edited, 
            "-o", hdr_dv_hevc] #5

        logging.info("Injection process begins...")
        logging.info(f"Files used: \n\t{file_pair["HDR_FILE"]["path"]}\n\t{file_pair["DV_FILE"]["path"]}")

        self.run(cmdExtractHDRMKV, title="Extracting HDR video:\t\t")
        if isDVmp4: self.run(cmdExtractDV, title="Extracting DV video:\t\t", total=file_pair["DV_FILE"]["frameCount"])
        else: self.run(cmdExtractDVMKV, title="Extracting DV video:\t\t")
        self.run(cmdExtractRPU, title="Extracting RPU from DV file:\t")
        self.run(cmdRPUEdit, "Modifying RPU-file:\t\t")
        self.run(cmdRPUInject, "Injecting RPU into HDR file:\t")
        self._merge(file_pair["HDR_FILE"]["path"], hdr_dv_hevc)

    @staticmethod
    def _run_dovi_tool(cmd, progress:Progress, title:str):
        total = 100
        seconds = False
        if "inject-rpu" in cmd: total = 200
        if "editor" in cmd: total = 1
        task = progress.add_task(title, total=total, status="")
        ansi_clean = re.compile(r"\x1b\[[\?\d;]*[A-Za-z]|\r|\n")
        proc = PtyProcess.spawn(cmd)
        output = "ERROR"
        try:
            while proc.isalive():
                output = ansi_clean.sub("", proc.read(256)).strip()
                m = re.search(r'(\d+)%', output)
                if "Rewriting file with interleaved RPU NALs.." in output: seconds = True
                if output and not m:
                    if output == "Done.":
                        progress.update(task_id=task, status="[green]Done")
                    else:
                        progress.update(task_id=task, status=output)
                elif m:
                    percentage = int(m.group(1))
                    if seconds: percentage += 100
                    if percentage == total:
                        progress.update(task_id=task, status="[green]Done")
                    progress.update(task_id=task, completed=percentage)
        except EOFError: pass

        if proc.exitstatus == 1:
            logging.error(f"The \"{title.replace(":", "")}\" command failed: {output}")
            progress.remove_task(task)
        else:
            if "editor" in cmd:
                progress.update(task_id=task, completed=total, status="[green]Done")

    @staticmethod
    def _run_cmd(cmd, progress:Progress, title:str, total:float):
        task = progress.add_task(title, total=total, status="")
        data = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            shell=True, 
            text=True
        )
        completed = 0
        for line in data.stdout: # type: ignore
            if "#GUI#progress" in line:
                completed = int(line.replace("#GUI#progress ","").replace("%",""))
            elif "frame=" in line:
                completed = int(line.replace("frame=",""))/total
            if completed:
                progress.update(task, completed=completed)
        if cmd[0] == FFMPEG and data.returncode == 0:
            progress.update(task, completed=total)

    def run(self, cmd, title="", total=100):
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(compact=True),
            TextColumn("{task.fields[status]}"),
            refresh_per_second=10
        ) as progress:
            try:
                if cmd[0] in [FFMPEG, MKVEXTRACT, MKVMERGE]:
                    self._run_cmd(cmd, progress, title, total)
                elif cmd[0] == DOVI_TOOL:
                    self._run_dovi_tool(cmd, progress, title)
            except subprocess.CalledProcessError:
                logging.error("Command failed, The process of this file will FAIL!")
                raise RuntimeError
            except KeyboardInterrupt:
                logging.error("Command interupted, The process of this file will FAIL!")
                raise InterruptedError

    def _merge(self, file:Path, DoVi:Path):
        file_out = file.with_name(file.name.replace(".mkv", "_HDR_DV.mkv"))
        cmdMerge = [
            MKVMERGE,
            "--gui-mode",
            "-o", file_out,
            "--no-video",
            file,
            DoVi
        ]

        self.run(cmdMerge, "Multiplexing hybrid file: \t")
        logging.info("Files sucessfully combined")

    def inject(self):
        for match in self.matchedFiles: 
            try: self._main(match)
            except RuntimeError:
                logging.error("Multiplexing of file FAILED")
            except InterruptedError:
                logging.error("Multiplexing of file FAILED because of Human interuption")
            finally:
                self.cleanUp()

    @staticmethod
    def mkTemp():
        temp_workdir.mkdir(exist_ok=True)
        logging.debug(f"Temp folder created at: {temp_workdir}")

    @staticmethod
    def cleanUp():
        rmtree(temp_workdir, ignore_errors=True)
        logging.debug(f"Temp folder was removed")

class CompareWindow():

    def __init__(self, hdr:dict, dv:dict, isHybrid:bool) -> None:
        self.window = tkinter.Tk()
        self.font = tkinter.font.Font(weight="bold")
        self.color_mode = "D"
        self.ref_int = tkinter.IntVar(value=1000)
        self.shifted_int = tkinter.IntVar(value=0)
        self.dv_file = dv["path"]
        self.dv_fps = dv["frameRate"]
        self.hdr_file = hdr["path"]
        self.hdr_fps = hdr["frameRate"]
        self.isHybrid = isHybrid
        self.total_ref = hdr["frameCount"]

        # Variable to track scheduled resize
        self._resize_after_id = None

        self.active_image, self.blend, self.difference = self._generate_image(self.ref_int.get(), self.shifted_int.get())
        self._window_init()

    @property
    def shifted_frames(self) -> int:
        return self.shifted_int.get()

    def _validate_ref_int(self, action:str, text:str) -> bool:
        if action in ["1","0"]:
            if text.isdigit():
                if int(text) > self.total_ref:
                    self.window.after_idle(lambda: self.ref_int.set(self.total_ref))
                if int(text) <= self.total_ref:
                    self.window.after_idle(lambda: self.ref_int.set(int(text)))
                return True
            elif text == "":
                self.window.after_idle(lambda: self.ref_int.set(0))
                self.window.after_idle(lambda: self.ref_entry.icursor(1))
                return True
            else:
                return False
        else:
            return True

    def _validate_int(self, action:str, text:str, validate_state:str) -> bool:
        if validate_state == "key":
            valid_int = re.compile(r"^[+-]?[0-9]+$|^-{1}$")
            return bool(valid_int.match(text)) if action == "1" else True
        else:
            valid_int = re.compile(r"^[+-]?[0-9]+$")
            if not valid_int.match(text) or text == "":
                self.window.after_idle(lambda: self.shifted_int.set(0))
            return bool(valid_int.match(text)) if action in ["1","0"] else True
            
    def _button_init(self) -> None:
        # Open in photos
        show_image_btn = tkinter.Button(self.window, text="Open picture", command=self._show_image)
        show_image_btn.grid(column=0, row=0, sticky=tkinter.W, padx=5, pady=5)
        
        # Switch view
        switch_btn = tkinter.Button(self.window, text="Switch view", command=self._switch_view)
        switch_btn.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=5)
        
        # Submit value
        done_btn = tkinter.Button(self.window, text="Done", command=self._done)
        done_btn.grid(column=2, row=1, sticky=tkinter.E, padx=5, pady=5)

    def _entry_init(self) -> None:
        # Validator
        valid_ref_int = (self.window.register(self._validate_ref_int),"%d", "%P")
        valid_int = (self.window.register(self._validate_int),"%d", "%P", "%V")
        
        # Reference frame
        ref_label = tkinter.Label(
            self.window, 
            text=f"Frame to refrence in HDR video (total: {self.total_ref}):", 
            bg="black", 
            fg="white", 
            font=self.font
        )
        ref_label.grid(column=0, row=0, sticky=tkinter.E, padx=5, pady=5)
        self.ref_entry = tkinter.Entry(
            self.window, 
            validate = "all",
            validatecommand = valid_ref_int, 
            textvariable=self.ref_int
        )
        self.ref_entry.bind("<Return>", self._update_image)
        self.ref_entry.grid(column=1, row=0, sticky=tkinter.W, padx=5, pady=5)

        # Other frame
        shifted_label = tkinter.Label(
            self.window, 
            text="Frames to shift Dolby Vision Layer with:", 
            bg="black", 
            fg="white", 
            font=self.font
        )
        shifted_label.grid(column=0, row=1, sticky=tkinter.E, padx=5, pady=5)
        self.shifted_entry = tkinter.Entry(
            self.window, 
            validate = "all",
            validatecommand = valid_int, 
            textvariable=self.shifted_int
        )
        self.shifted_entry.bind("<Return>", self._update_image)
        self.shifted_entry.grid(column=1, row=1, sticky=tkinter.W, padx=5, pady=5)

    def _canvas_init(self) -> None:
        image = ImageTk.PhotoImage(self.active_image)
        self.canvas = tkinter.Canvas(
            self.window, 
            width=image.width(), 
            height=image.height(), 
            bg="black"
        )
        self.canvas.grid(column=0, row=3, columnspan=3, padx=5, pady=5)
        self.image_id = self.canvas.create_image(0, 0, image=image, anchor="nw")

    def _window_init(self):
        # --- Main Window config ---
        self.window.title("Frame Compare")
        self.window.iconbitmap(str(Path(__file__).parent.resolve().joinpath("icon.ico")))
        self.window.geometry("1200x800")
        self.window.minsize(700,420)
        self.window.configure(bg="black", padx=10, pady=10)
        self.window.columnconfigure(0, weight=1)
        self.window.columnconfigure(1, weight=1)
        self.window.columnconfigure(2, weight=0)

        self._button_init()
        self._entry_init()

        self._canvas_init()
        self.window.bind("<Configure>", self._on_resize)

        # --- Focus the Window ---
        self.window.lift()
        self.window.attributes("-topmost",True)
        self.window.protocol("WM_DELETE_WINDOW", self._done)
        self.window.after_idle(self.window.attributes,"-topmost",False)
        self.window.mainloop()
    
    def _done(self):
        self.window.quit()
        self.window.destroy()

    def _update_image(self, event):
        logging.debug(f"Refrence frame: {self.ref_int.get()}")
        logging.debug(f"Shifted frames: {self.shifted_int.get()}")
        
        self.active_image, self.blend, self.difference = self._generate_image(self.ref_int.get(), self.shifted_int.get())
        self._resize_image()
    
    def _show_image(self):
        logging.info("Opening image in default photo viewer")
        self.active_image.show()

    def _on_resize(self, event):
        # Cancel any scheduled resize
        if self._resize_after_id:
            self.window.after_cancel(self._resize_after_id)

        # Schedule a new resize after 200 ms (debounce)
        self._resize_after_id = self.window.after(150, self._resize_image)

    def _resize_image(self):
        global new_image, resized_image
        win_width = self.window.winfo_width() - 40
        win_height = self.window.winfo_height() - 110
        resized_height = int((self.active_image.height/self.active_image.width)*win_width)
        if resized_height > win_height:
            resized_width = int((self.active_image.width/self.active_image.height)*win_height)
            resized_image = self.active_image.resize((resized_width, win_height), Image.Resampling.LANCZOS)
            self.canvas.config(width=resized_width, height=win_height)
        else:  
            resized_image = self.active_image.resize((win_width, resized_height), Image.Resampling.LANCZOS)
            self.canvas.config(width=win_width, height=resized_height)
        new_image = ImageTk.PhotoImage(resized_image)
        self.canvas.itemconfigure(self.image_id, image=new_image)

        self._resize_after_id = None  # Reset

    def _switch_view(self):
        if self.color_mode == "D":
            logging.debug("Switching to Blended image")
            self.active_image = self.blend
            self.color_mode = "B"
            self._resize_image()
        else:
            logging.debug("Switching to Difference image")
            self.active_image = self.difference
            self.color_mode = "D"
            self._resize_image()
    
    def _generate_image(self, ref:int, shift:int) -> tuple[Image.Image, Image.Image, Image.Image]:
        logging.debug("Generating images to compare...")

        vf_HDR = "zscale=t=linear,tonemap=hable,zscale=p=709:t=709:m=709"
        vf_DV = "libplacebo=tonemapping=auto,zscale=t=linear,tonemap=hable,zscale=p=709:t=709:m=709" 
        ss_hdr = str(ref / self.hdr_fps)
        ss_dv = str((ref - shift) / self.dv_fps)

        ColorMerger.mkTemp()
        hdr_out = temp_workdir.joinpath("HDR.bmp")
        dv_out = temp_workdir.joinpath("DV.bmp")

        hdr_cmd = [
            FFMPEG,
            "-hide_banner",
            "-v", "error",
            "-y", 
            "-ss", ss_hdr,
            "-i", self.hdr_file,
            "-qscale:v", "1", 
            "-vf", vf_HDR,
            "-vframes", "1",
            hdr_out
        ]

        dv_cmd = [
            FFMPEG, 
            "-hide_banner", 
            "-v", "error",
            "-y", 
            "-ss", ss_dv,
            "-i", self.dv_file,
            "-qscale:v", "1", 
            "-vf", vf_HDR if self.isHybrid else vf_DV,
            "-vframes", "1",
            dv_out
        ]

        logging.debug("Generating HDR image...")
        try: 
            subprocess.run(hdr_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e: 
            logging.error(f"Failed to generate HDR screencapture | ERROR:{e}")

        logging.debug("Generating DV image...")
        try: 
            subprocess.run(dv_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e: 
            logging.error(f"Failed to generate DV screencapture | ERROR:{e}")
        
        logging.debug("Processing Images...")
        HDR_img = Image.open(hdr_out)
        DV_img = Image.open(dv_out)
        HDR_w, HDR_h = HDR_img.size
        DV_w, DV_h = DV_img.size
        crop = abs(HDR_h-DV_h)/2

        if HDR_img.height < DV_img.height: DV_img = DV_img.crop((0, crop, DV_w, DV_h-crop))
        elif HDR_img.height > DV_img.height: HDR_img = HDR_img.crop((0, crop, HDR_w, HDR_h-crop))

        difference = Image.blend(DV_img, HDR_img, 0.5)
        blend = ImageChops.difference(DV_img.convert('L'), HDR_img.convert('L'))
        logging.debug("Processing done!")

        active_image = difference if self.color_mode == "D" else blend
        
        return active_image, blend, difference

if __name__ == "__main__": 
    injector = ColorMerger(collect_files(args.files))
    injector.inject()
