import subprocess
import logging
import os
import json
import argparse
import inquirer
import shutil
import time

import tkinter.filedialog
import tkinter.font
import tkinter
from PIL import ImageTk, Image, ImageChops
from pymediainfo import MediaInfo
from alive_progress import alive_bar

parser = argparse.ArgumentParser(prog="Dolby Vision + HDR", description="A program to combine HDR videos with Dolby Vison videos for a Dolby Vison file with HDR fallback", epilog="Report bugs to Swedish-Wiking@GitHub")
parser.add_argument("input", metavar="I", nargs="*", help="List of file/folders to use as input")
parser.add_argument("-logL", dest="logL", choices=["debug", "info", "error"], help="Set verbose level")
parser.add_argument("-maxdif", dest="maxdif", type=int, help="Set maxed allowed frames to differ between videos")
args = parser.parse_args()

logging.basicConfig(format="%(levelname)s:\t%(message)s", level=logging.INFO)
if args.logL == "debug": logging.basicConfig(level=logging.DEBUG)
elif args.logL == "info": logging.basicConfig(level=logging.INFO)
elif args.logL == "error": logging.basicConfig(level=logging.ERROR)

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
_temp = os.path.join(__location__, "temp\\")
_bin = os.path.join(__location__, "bin\\")
mkvmerge = os.path.join(_bin, "mkvmerge.exe")
mkvextract = os.path.join(_bin, "mkvextract.exe")
dovi_Tool = os.path.join(_bin, "dovi_tool.exe")

def createTempDir():
    os.makedirs(_temp, exist_ok=True)
    logging.debug(f"Temp folder created at: {_temp}")

class image_compare():
    def __init__(self, hdr, dv):
        self.dv_file = dv
        self.hdr_file = hdr
        self.base_refrence = 1000
        self.shifted_frames = 0
        createTempDir()
        self.active_image_lb = "D"
        self.active_image = self.create_thumbnails()
        icon_file = os.path.join(__location__,"icon.png")
        
        #Initialization
        self.window = tkinter.Tk()
        icon = ImageTk.PhotoImage(file=str(icon_file))
        tk_font = tkinter.font.Font(weight="bold")
        
        #Window config
        self.window.title("Frame Compare")
        self.window.iconphoto(True, icon)
        self.window.geometry("1200x800")
        self.window.minsize(700,420)
        self.window.configure(bg='black', padx=10, pady=10)
        self.window.columnconfigure(0, weight=1)
        self.window.columnconfigure(1, weight=1)
        self.window.columnconfigure(2, weight=0)
        
        #Buttons
        show_image_btn = tkinter.Button(self.window, text="Open picture", command=self.show_image)
        show_image_btn.grid(column=0, row=0, sticky=tkinter.W, padx=5, pady=5)
        switch_btn = tkinter.Button(self.window, text="Switch view", command=self.switch)
        switch_btn.grid(column=0, row=1, sticky=tkinter.W, padx=5, pady=5)
        done_btn = tkinter.Button(self.window, text="Done", command=self.done)
        done_btn.grid(column=2, row=1, sticky=tkinter.E, padx=5, pady=5)

        #Entries
        v_base, v_shift = tkinter.IntVar(), tkinter.IntVar()
        vcmd = (self.window.register(self.validate_int),'%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')
        base_lb = tkinter.Label(self.window, text=f"Base frame to refrence (total: {hdr["frameCount"]}):", bg="black", fg="white", font=tk_font)
        base_lb.grid(column=0, row=0, sticky=tkinter.E, padx=5, pady=5)
        shift_lb = tkinter.Label(self.window, text="Frames to shift DV Layer:", bg="black", fg="white", font=tk_font)
        shift_lb.grid(column=0, row=1, sticky=tkinter.E, padx=5, pady=5)
        self.base_entry = tkinter.Entry(self.window, validate = 'key', validatecommand = vcmd, text=v_base)
        self.base_entry.bind('<Return>', self.shift_Base_Frame)
        self.base_entry.grid(column=1, row=0, sticky=tkinter.W, padx=5, pady=5)
        self.shift_entry = tkinter.Entry(self.window, validate = 'key', validatecommand = vcmd, text=v_shift)
        self.shift_entry.bind('<Return>', self.shift_DV_Layer)
        self.shift_entry.grid(column=1, row=1, sticky=tkinter.W, padx=5, pady=5)
        v_base.set(self.base_refrence)
        v_shift.set(0)

        #Image Canvas
        image = ImageTk.PhotoImage(self.active_image)
        imageWidth = image.width()
        imageHeight = image.height()
        self.canvas = tkinter.Canvas(self.window, width=imageWidth, height=imageHeight, bg="black")
        self.canvas.grid(column=0, row=3, columnspan=3, padx=5, pady=5)
        self.image_id = self.canvas.create_image(0, 0, image=image, anchor='nw')
        self.canvas.bind('<Configure>', self.resize_image)
        
        #Open Window
        self.window.lift()
        self.window.attributes("-topmost",True)
        self.window.after_idle(self.window.attributes,"-topmost",False)
        self.window.mainloop()
    
    def validate_int(self, action, index, value_if_allowed, prior_value, text, validation_type, trigger_type, widget_name):
        if(action=='1'):
            if text in '0123456789-+':
                try:
                    int(value_if_allowed)
                    return True
                except ValueError: return False
            else: return False
        else: return True

    def create_thumbnails(self):
        logging.debug("Generating images to compare...")
        vf_HDR = "zscale=t=linear,tonemap=hable,zscale=p=709:t=709:m=709"
        vf_DV = "libplacebo=tonemapping=auto,zscale=t=linear,tonemap=hable,zscale=p=709:t=709:m=709" 
        ss_hdr = str(self.base_refrence / self.hdr_file["frameRate"])
        ss_dv = str((self.base_refrence - self.shifted_frames) / self.dv_file["frameRate"])
        hdr_out = os.path.join(_temp, "HDR.bmp")
        dv_out = os.path.join(_temp, "DV.bmp")

        hdr_cmd = ["ffmpeg", 
            "-hide_banner", 
            "-v", "error",
            "-y", 
            "-ss", ss_hdr,
            "-i", self.hdr_file["path"],
            "-qscale:v", "1", 
            "-vf", vf_HDR,
            "-vframes", "1",
            hdr_out
        ]

        dv_cmd = ["ffmpeg", 
            "-hide_banner", 
            "-v", "error",
            "-y", 
            "-ss", ss_dv,
            "-i", self.dv_file["path"],
            "-qscale:v", "1", 
            "-vf", vf_DV,
            "-vframes", "1",
            dv_out
        ]

        logging.debug("Generating HDR image...")
        try: subprocess.run(hdr_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e: logging.error(f"Failed to generate HDR screencapture | ERROR:{e}")
        logging.debug("Generating DV image...")
        try: subprocess.run(dv_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e: logging.error(f"Failed to generate DV screencapture | ERROR:{e}")

        logging.debug("Processing Images...")
        HDR_img = Image.open(hdr_out)
        DV_img = Image.open(dv_out)
        HDR_w, HDR_h = HDR_img.size
        DV_w, DV_h = DV_img.size
        crop = abs(HDR_h-DV_h)/2

        if HDR_img.height < DV_img.height: DV_img = DV_img.crop((0, crop, DV_w, DV_h-crop))
        elif HDR_img.height > DV_img.height: HDR_img = HDR_img.crop((0, crop, HDR_w, HDR_h-crop))

        self.difference_img = Image.blend(DV_img, HDR_img, 0.5)
        self.blend_img = ImageChops.difference(DV_img.convert('L'), HDR_img.convert('L'))
        logging.debug("Processing done!")

        if self.active_image_lb == "D": self.active_image = self.difference_img
        elif self.active_image_lb == "B":self.active_image = self.blend_img
        
        return self.difference_img
    
    def shift_DV_Layer(self, event):
        logging.debug(f"Dolby Vision Layer shifted {self.shift_entry.get()} frames")
        self.shifted_frames = int(self.shift_entry.get())
        self.base_refrence = int(self.base_entry.get())
        self.create_thumbnails()
        self.resize_image("")

    def shift_Base_Frame(self, event):
        logging.debug(f"Changed refrence frame to: {self.base_entry.get()}")
        self.shifted_frames = int(self.shift_entry.get())
        self.base_refrence = int(self.base_entry.get())
        self.create_thumbnails()
        self.resize_image("")
        
    def resize_image(self, e):
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

    def show_image(self):
        logging.info("Opening image in default photo viewer")
        self.active_image.show()

    def done(self):
        self.window.quit()
        self.window.destroy()

    def switch(self):
        if self.active_image_lb == "D":
            logging.debug("Switching to Blended image")
            self.active_image = self.blend_img
            self.active_image_lb = "B"
            self.resize_image("")
        elif self.active_image_lb == "B":
            logging.debug("Switching to Difference image")
            self.active_image = self.difference_img
            self.active_image_lb = "D"
            self.resize_image("")

def file_list():
    file_paths = list()
    filetypes = (("Video files", ".mkv .mp4"), ("Matroska files", ".mkv"), ("MPEG-4 files", ".mp4"), ("All files", "*.*"))

    if args.input == []:
        file_ask = tkinter.Tk()
        file_ask.withdraw()
        icon = ImageTk.PhotoImage(file=str(os.path.join(__location__,"icon.png")))
        file_ask.iconphoto(True, icon)
        files = tkinter.filedialog.askopenfilenames(parent=file_ask, title="Select files", multiple=True, filetypes=filetypes)
        file_ask.destroy()
    else: files = args.input
    
    for path in files:
        if os.path.isfile(path): file_paths.append(path)
        else:
            for root, directories, files in os.walk(path):
                for filename in files:
                    file_ext = os.path.splitext(filename)[1]
                    accepted_ext = {'.mkv', '.mp4'}
                    if file_ext in accepted_ext:
                        filepath = os.path.join(root, filename)
                        file_paths.append(filepath)
    if len(file_paths) <= 1: 
        logging.error("No files chosen")
        exit(code=1)
    return file_paths

def check_for_ffmpeg():
    try:
        subprocess.check_call(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        logging.error("FFmpeg installed but something whent wrong re-run script")
        exit(code=1)
    except OSError:
        logging.error("FFmpeg not installed, please install and re-run script")
        exit(code=1)

def is_integer(n):
    try: float(n)
    except ValueError: return False
    else: return float(n).is_integer()

def parse_metadata(data, file):
    json_data = json.loads(data)
    logging.debug(json_data)
    json_data = json_data["streams"][0]
    width = int(json_data["width"])
    height = int(json_data["height"])
    fps = json_data["avg_frame_rate"].split("/")
    fps = int(fps[0]) / int(fps[1])

    try: framCount = int(json_data["tags"]["NUMBER_OF_FRAMES"])
    except:
        try: framCount = int(json_data["tags"]["NUMBER_OF_FRAMES-eng"])
        except:
            try: framCount = int(json_data["nb_frames"])
            except:
                logging.warning("Framerate was not found in ffprobe data, using MediaInfo")
                logging.warning("Analysis may take longer")
                media_info = MediaInfo.parse(file)
                for track in media_info.tracks: 
                    if track.track_type == "Video": framCount = int(track.frame_count)
    
    try: 
        if json_data["side_data_list"][0]["rpu_present_flag"] == 1: 
            try:
                if json_data["color_transfer"] == "smpte2084": colorProfile = "HDR+DV"
            except: colorProfile = "DV"
    except:
        try: 
            if json_data["color_transfer"] == "smpte2084": colorProfile = "HDR"
        except: colorProfile = "None"
    
    return {"frameCount": framCount, "colorProfile": colorProfile, "pxWidth": width, "pxHeight": height, "frameRate": fps}

def analyze_files(files):
    metadata_list = list()
    for file in files:
        name = os.path.basename(file)
        logging.info(f"Analyzing {name}...")
        probe_cmd = ["ffprobe",
            "-hide_banner",
            "-loglevel", "fatal",
            "-show_error",
            "-show_streams",
            "-select_streams", "v:0",
            "-show_private_data",
            "-print_format", "json",
            file]

        try:
            data = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if data.returncode != 0:
                logging.warning(f"File could not be analyzed: {data.stderr}")
                break
        except: 
            logging.warning(f"File could not be analyzed: {data.stderr}")
            break

        parsed_data = parse_metadata(data.stdout.decode('utf-8'), file)
        logging.info("Sucessfully analyzed file!")
        metadata_list.append({"name": name, "path": file} | parsed_data)
    

    cColorP = set()
    for media in metadata_list: cColorP.add(media["colorProfile"])
    if "HDR" in cColorP: logging.info("HDR Media:")
    for media in metadata_list:
        if media["colorProfile"] == "HDR":
            logging.info(f"{media["name"]}:\n\tFrameCount: {media["frameCount"]}\n\tWidth: {media["pxWidth"]}\n\tHeight: {media["pxHeight"]}\n\tFrameRate: {media["frameRate"]}")
    if "DV" in cColorP: logging.info("Dolby Vision Media:")
    for media in metadata_list:
        if media["colorProfile"] == "DV":
            logging.info(f"{media["name"]}:\n\tFrameCount: {media["frameCount"]}\n\tWidth: {media["pxWidth"]}\n\tHeight: {media["pxHeight"]}\n\tFrameRate: {media["frameRate"]}")
    if "HDR+DV" in cColorP: logging.info("HDR + DV Media:")
    for media in metadata_list:
        if media["colorProfile"] == "HDR+DV":
            logging.info(f"{media["name"]}:\n\tFrameCount: {media["frameCount"]}\n\tWidth: {media["pxWidth"]}\n\tHeight: {media["pxHeight"]}\n\tFrameRate: {media["frameRate"]}")

    return metadata_list, cColorP

def frame_seeker(hdr, dv):
    logging.warning("Dolby Vision layer probably needs to be delayed")
    isManual = inquirer.prompt([inquirer.Confirm("continue", message="Do you want to input pre-calculated frame-shift", default=False)])["continue"]
    if isManual:
        while True:
            delayed_frames = input("Input frames to shift Dolby Vision layer with: ")
            if(is_integer(delayed_frames) == False): logging.warning("Please input a valid number")
            else: delayed_frames = int(delayed_frames); break
    else:
        comparer = image_compare(hdr, dv)
        delayed_frames = comparer.shifted_frames
    logging.info(f"Dolby Vision layer is shifted by {delayed_frames} frames")
    return delayed_frames

def match_files(data_list):
    matching_files = list()
    HDRs = [(media) for media in data_list if media["colorProfile"] == "HDR"]
    logging.debug(HDRs)
    DVs = [(media) for media in data_list if media["colorProfile"] == "DV"] + [(media) for media in data_list if media["colorProfile"] == "HDR+DV"]
    logging.debug(DVs)
    if args.maxdif != None: maxDif = int(args.maxdif)
    else:
        while True:
            maxDif = input(f"Input max allowed differance in frames: ")
            if(is_integer(maxDif) == False): logging.warning("Please input a valid number")
            else: maxDif = int(maxDif); break
    
    logging.info("Matching files...")
    for hdr_file in HDRs:
        miss = 0
        logging.info(f"Trying to match: {hdr_file["name"]}")
        for dv_file in DVs:
            absDif = abs(hdr_file["frameCount"] - dv_file["frameCount"])
            if absDif == 0:
                logging.info(f"Perfect match found with: {dv_file["name"]}")
                isAutomatic = inquirer.prompt([inquirer.Confirm("auto", message="Want to frame match anyways?", default=False)])["auto"]
                if isAutomatic: frames_to_delay = frame_seeker(hdr_file, dv_file)
                else: frames_to_delay = 0
                match = {"HDR_FILE": hdr_file, "DV_FILE": dv_file, "framesToDelay": frames_to_delay}
                matching_files.append(match)
                break
            elif(absDif <= maxDif):
                logging.info(f"Match found but with a difference of: {absDif} frames, file matched with: {dv_file["name"]}")
                isMatch = inquirer.prompt([inquirer.Confirm("continue", message="Is it a match?", default=False)])["continue"]
                if isMatch:
                    frames_to_delay = frame_seeker(hdr_file, dv_file)
                    match = {"HDR_FILE": hdr_file, "DV_FILE": dv_file, "framesToDelay": frames_to_delay}
                    matching_files.append(match)
                else: logging.info("Trying another ")
            else: miss += 1
            if miss == len(DVs): 
                logging.warning(f"No match found for: {hdr_file["name"]}")
    
    logging.info("Matching process completeded")
    logging.debug(matching_files)
    return matching_files

def run_cmd(cmd, title="", total=100):
    try: 
        if cmd[0] == "ffmpeg" or cmd[0] == mkvextract or cmd[0] == mkvmerge:
            with alive_bar(title=title, bar="filling", spinner="waves", manual=True, total=total, stats=False, monitor="{percent:,.1%}") as bar:
                data = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
                for line in data.stdout:
                    if "#GUI#progress" in line:
                        progress = int(line.replace("#GUI#progress ","").replace("%",""))/100
                        bar(progress)
                    elif "frame=" in line: 
                        bar(int(line.replace("frame=",""))/total)
                if cmd[0] == "ffmpeg": bar(1)
        else:
            with alive_bar(title=title, bar="filling", spinner="waves", manual=True, total=total, stats=False, monitor="{percent:,.1%}") as bar:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
                bar(1)

    except subprocess.CalledProcessError: 
        logging.error("Command failed, The process of this file will FAIL!")
        raise RuntimeError
    except KeyboardInterrupt: 
        logging.error("Command interupted, The process of this file will FAIL!")
        raise InterruptedError

def remux_files(main_file, DV_injected):
    file_out = os.path.join(os.path.dirname(main_file), os.path.basename(main_file).replace(".mkv", "_HDR_DV.mkv"))
    cmdMerge = [mkvmerge,
        "--gui-mode",
        "-o", file_out,
        "--no-video",
        main_file,
        DV_injected]

    run_cmd(cmdMerge, "Multiplexing hybrid file: \t")
    logging.info("Files sucessfully combined")

def injectDoVi(file_pair):
    createTempDir()
    rpu_json = os.path.join(_temp,"RPU.json")
    rpu = os.path.join(_temp,"RPU.bin")
    rpu_edited = os.path.join(_temp,"RPU_EDITED.bin")
    hdr_hevc = os.path.join(_temp,"HDR.hevc")
    dv_hevc = os.path.join(_temp,"DV.hevc")
    hdr_dv_hevc = os.path.join(_temp,"HDR_DV.hevc")

    if str(os.path.splitext(file_pair["DV_FILE"]["path"])[1]) == ".mp4": isDVmp4 = True
    else: isDVmp4 = False
    
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
        mkvextract, 
        "tracks", 
        file_pair["HDR_FILE"]["path"], 
        "0:" + str(hdr_hevc), 
        "--gui-mode"] #1
    cmdExtractDVMKV = [
        mkvextract, 
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
        dovi_Tool, 
        "-m", "3", 
        "extract-rpu", 
        dv_hevc, 
        "-o", rpu] #3
    cmdRPUEdit = [
        dovi_Tool, 
        "editor",
        "-i", rpu, 
        "-j", rpu_json, 
        "-o", rpu_edited] #4
    cmdRPUInject = [
        dovi_Tool, 
        "inject-rpu",
        "-i", hdr_hevc, 
        "--rpu-in", rpu_edited, 
        "-o", hdr_dv_hevc] #5

    logging.info("Injection process begins...")
    logging.info(f"Files used: \n\t{file_pair["HDR_FILE"]["path"]}\n\t{file_pair["DV_FILE"]["path"]}")

    run_cmd(cmdExtractHDRMKV, title="Extracting HDR video:\t\t")
    if isDVmp4: run_cmd(cmdExtractDV, title="Extracting DV video:\t\t", total=file_pair["DV_FILE"]["frameCount"])
    else: run_cmd(cmdExtractDVMKV, title="Extracting DV video:\t\t")
    run_cmd(cmdExtractRPU, title="Extracting RPU from DV file:\t")
    run_cmd(cmdRPUEdit, "Modifying RPU-file:\t\t")
    run_cmd(cmdRPUInject, "Injecting RPU into HDR file:\t")
    remux_files(file_pair["HDR_FILE"]["path"], hdr_dv_hevc)
    try: shutil.rmtree(_temp)
    except: logging.warning("Could not delete temp folder")

def main():
    check_for_ffmpeg()
    files = file_list()
    file_data_list, cColorP = analyze_files(files)
    if ("DV" not in cColorP and "HDR+DV" not in cColorP) or not "HDR" in cColorP:
        logging.error("Not enough files with HDR or DV layers")
        exit(code=1)
    matched_files = match_files(file_data_list)
    for match in matched_files: 
        try: injectDoVi(match)
        except RuntimeError: logging.error("Multiplexing of file FAILED")
        except InterruptedError: logging.error("Multiplexing of file FAILED because of Human interuption")
        else: 
            try: shutil.rmtree(_temp)
            except: logging.warning("Could not delete temp folder")

if __name__ == "__main__": main()