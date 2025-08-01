import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2
import json, os, sys, socket

# Unique port for your app (must not conflict with real services)
PORT = 65432
LOCK_SOCKET = None

def check_single_instance():
    global LOCK_SOCKET
    try:
        LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        LOCK_SOCKET.bind(('127.0.0.1', PORT))
    except socket.error:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showwarning("Already Running", "This application is already running.")
        sys.exit()

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "camera_config.json")

# Initial default camera URLs (will update from config input)
CAMERA_URLS = {
    "Camera 1": "",
    "Camera 2": "",
    "Camera 3": "",
    "Camera 4": ""
}

CONFIG_FILE = "camera_config.json"

class CCTVApp:
    def load_camera_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    for cam in CAMERA_URLS:
                        if cam in data:
                            CAMERA_URLS[cam] = data[cam]
            except Exception as e:
                print(f"[ERROR] Failed to load config: {e}")

    def __init__(self, root):
        self.root = root
        self.root.title("🚨 CCTV Live Viewer")
        self.root.configure(bg="white")
        self.root.geometry("1200x700")
        #tk.Label(root, bg="white", height=1).pack()
        self.after_id = None
        self.load_camera_config()
        self.grid_caps = {}
        self.grid_threads = {}
        self.grid_labels = {}
        self.grid_frames = {}
        self.camera_buttons = {}  # Track each camera button
        self.selected_camera = None

        # Top bar with camera buttons and config
        button_bar = tk.Frame(root, bg="white")
        button_bar.pack(fill="x", padx=20, pady=0)

        # Left-side buttons
        left_buttons = tk.Frame(button_bar, bg="white")
        left_buttons.pack(side="left")

        for cam in ["Camera 1", "Camera 2", "Camera 3", "Camera 4"]:
            btn = ttk.Button(left_buttons, text=cam, command=lambda c=cam: self.on_camera_click(c))
            btn.pack(side="left", padx=5)
            self.camera_buttons[cam] = btn

        # # Add "All Cameras" button
        # all_btn = ttk.Button(left_buttons, text="All Cameras", command=self.on_all_cameras_click)
        # all_btn.pack(side="left", padx=5)
        # self.camera_buttons["All Cameras"] = all_btn
        
        # Right-side config button
        right_buttons = tk.Frame(button_bar, bg="white")
        right_buttons.pack(side="right")

        self.config_button = ttk.Button(right_buttons, text="⚙️ Config", command=self.on_config_click)
        self.config_button.pack(side="right", padx=5)


        # Single video area
        self.video_frame = tk.Frame(root, bg="#dddddd")
        self.video_frame.pack(fill="both", expand=True, padx=10, pady=10)


        self.video_label = tk.Label(self.video_frame, bg="#eeeeee")
        self.video_label.pack(fill="both", expand=True)


        # Streaming state
        self.current_camera = None
        self.running = False
        self.start_stream("Camera 1")
        self.update_button_styles("Camera 1")

        # Auto-close after 5 minutes
        self.root.after(300000, self.auto_close)

    def auto_close(self):
        self.on_closing()


    def on_config_click(self):
        self.open_config()
        self.update_button_styles("Config")


    def on_camera_click(self, cam_name):
        if cam_name == "All Cameras":
            self.show_all_cameras()
        else:
            self.start_stream(cam_name)

        self.update_button_styles(cam_name)

    # def on_all_cameras_click(self):
    #     self.show_all_cameras()
    #     self.update_button_styles("All Cameras")

    def update_button_styles(self, selected):
        self.selected_camera = selected

        for name, btn in self.camera_buttons.items():
            if name == selected:
                btn.configure(style="Selected.TButton")
            else:
                btn.configure(style="TButton")

        # Apply style to Config button
        if selected == "Config":
            self.config_button.configure(style="Selected.TButton")
        else:
            self.config_button.configure(style="TButton")



    def open_config(self):
        self.config_win = tk.Toplevel(self.root)
        self.config_win.title("Configure Cameras")
        self.config_win.geometry("500x640")

        self.config_win.configure(bg="white")
        self.config_widgets = []  # reset tracked widgets

        # Camera input sections
        self.cam_inputs = {}

        for cam in ["Camera 1", "Camera 2", "Camera 3", "Camera 4"]:
            section = tk.LabelFrame(self.config_win, text=cam, font=("Arial", 12, "bold"))
            section.pack(fill="x", padx=20, pady=15)
            self.config_widgets.append(section)

            ip_var = tk.StringVar()
            user_var = tk.StringVar()
            pass_var = tk.StringVar()

            real_password = ""  # this holds the actual password

            # Set saved values if available
            saved_url = CAMERA_URLS.get(cam, "")
            if saved_url.startswith("rtsp://") and "@" in saved_url:
                try:
                    creds, address = saved_url[7:].split("@")
                    user, pwd = creds.split(":")
                    ip = address.split(":")[0]
                    ip_var.set(ip)
                    user_var.set(user)
                    # (Don't set pass_var — keep it blank for security)
                    real_password = pwd
                    masked_pwd = "*" * len(pwd)
                    pass_var.set(masked_pwd)

                except Exception as e:
                    print(f"[WARN] Failed to parse URL for {cam}: {e}")


            # Add widgets to section
            widgets = [
                (tk.Label(section, text="IP Address:"), 0, 0),
                (tk.Entry(section, textvariable=ip_var, width=35), 0, 1),
                (tk.Label(section, text="Username:"), 1, 0),
                (tk.Entry(section, textvariable=user_var, width=35), 1, 1),
                (tk.Label(section, text="Password:"), 2, 0),
                (tk.Entry(section, textvariable=pass_var, show="*", width=35), 2, 1)
            ]

            for widget, r, c in widgets:
                widget.grid(row=r, column=c, padx=5, pady=4, sticky="w")
                self.config_widgets.append(widget)

            self.cam_inputs[cam] = {
                "ip": ip_var,
                "user": user_var,
                "pass": pass_var,
                "real_pass": real_password  # 🔒 secret stored separately
            }

        # Submit button
        submit_btn = ttk.Button(self.config_win, text="Submit", command=lambda: self.apply_config(self.config_win))
        submit_btn.pack(pady=20)
        self.config_widgets.append(submit_btn)

    def apply_config(self, window):
        # Clear current entries before updating (optional but safe)
        for cam in list(CAMERA_URLS):
            if cam not in self.cam_inputs:
                continue
            ip = self.cam_inputs[cam]["ip"].get().strip()
            user = self.cam_inputs[cam]["user"].get().strip()
            pwd = self.cam_inputs[cam]["real_pass"] or self.cam_inputs[cam]["pass"].get().strip()

            if ip and user and pwd:
                rtsp_url = f"rtsp://{user}:{pwd}@{ip}:554/Streaming/Channels/102"
                CAMERA_URLS[cam] = rtsp_url
            else:
                if cam in CAMERA_URLS:
                    del CAMERA_URLS[cam]

        # ✅ Save to JSON file ONCE
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(CAMERA_URLS, f, indent=4)
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")

        messagebox.showinfo("Success", "Camera settings saved.")
        window.destroy()
        self.start_stream("Camera 1")


    def start_stream(self, name):
        self.stop_stream()  # stop previous loop & release cap
        self.current_camera = name

        url = CAMERA_URLS.get(name, "").strip()
        if not url:
            messagebox.showerror("Missing URL", f"Details not configured for {name}")
            return

        print(f"[INFO] Connecting to {name}: {url}")
        self.cap = cv2.VideoCapture(url)

        if not self.cap or not self.cap.isOpened():
            messagebox.showerror("Stream Error", f"Unable to open stream for {name}")
            return

        self.running = True
        self.update_frame()

    def show_all_cameras(self):
        self.stop_stream()  # Stop single view

        # Clear video frame
        for widget in self.video_frame.winfo_children():
            widget.destroy()

        # Make video_frame act like a grid container that resizes
        self.video_frame.columnconfigure(0, weight=1)
        self.video_frame.columnconfigure(1, weight=1)
        self.video_frame.rowconfigure(0, weight=1)
        self.video_frame.rowconfigure(1, weight=1)

        self.running = True
        self.multi_caps = {}
        self.multi_labels = {}

        cams = ["Camera 1", "Camera 2", "Camera 3", "Camera 4"]
        row, col = 0, 0

        for cam in cams:
            url = CAMERA_URLS.get(cam, "").strip()
            if not url:
                continue

            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            for _ in range(5):
                cap.read()

            if not cap.isOpened():
                continue

            label = tk.Label(self.video_frame, bg="#eeeeee")
            label.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            label.update_idletasks()

            self.multi_caps[cam] = cap
            self.multi_labels[cam] = label

            col += 1
            if col > 1:  # 2 cameras per row
                col = 0
                row += 1

        self.update_all_cameras()


    def update_frame(self):
        if not self.running or not self.cap or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if ret:
            w = self.video_label.winfo_width()
            h = self.video_label.winfo_height()
            frame = cv2.resize(frame, (w, h))

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img)

            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

        # Schedule next frame & store ID so we can cancel later
        if self.running:
            self.after_id = self.video_label.after(1, self.update_frame)

    def update_all_cameras(self):
        if not self.running:
            return

        for cam, cap in self.multi_caps.items():
            ret, frame = cap.read()
            if ret:
                label = self.multi_labels[cam]
                w = label.winfo_width()
                h = label.winfo_height()
                if w > 0 and h > 0:
                    frame = cv2.resize(frame, (w, h))
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)

                    label.imgtk = imgtk
                    label.configure(image=imgtk)

        self.after_id = self.root.after(30, self.update_all_cameras)


    def stop_stream(self):
        self.running = False
        self.grid_running = False

        if self.after_id:
            try:
                self.root.after_cancel(self.after_id)
            except Exception as e:
                print(f"[WARNING] after_cancel error: {e}")
            self.after_id = None

        # Release single view capture
        if hasattr(self, "cap") and self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None

        # ✅ Safely handle grid view resources
        if hasattr(self, "grid_caps"):
            for cap in self.grid_caps.values():
                if cap and cap.isOpened():
                    cap.release()
            self.grid_caps.clear()

        if hasattr(self, "grid_threads"):
            self.grid_threads.clear()

        if hasattr(self, "grid_labels"):
            self.grid_labels.clear()

        if hasattr(self, "grid_frames"):
            self.grid_frames.clear()

        # Destroy old widgets
        for widget in self.video_frame.winfo_children():
            try:
                widget.destroy()
            except:
                pass

        # Recreate single video label
        self.video_label = tk.Label(self.video_frame, bg="#eeeeee")
        self.video_label.pack(fill="both", expand=True)


    def on_closing(self):
        self.stop_stream()
        if LOCK_SOCKET:
            try:
                LOCK_SOCKET.close()
            except:
                pass
        self.root.destroy()


if __name__ == "__main__":
    check_single_instance()

    root = tk.Tk()
    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 10), padding=6)
    style.configure("Selected.TButton",
                font=("Helvetica", 10, "bold"),
                padding=6,
                relief="solid",
                background="#0078D7",         # strong blue
                foreground="black",
                borderwidth=2)

    style.map("Selected.TButton",
            background=[("!disabled", "#0078D7")],
            foreground=[("!disabled", "black")])
    style.map("TButton",
        background=[("active", "#e6f0ff")])
    style.map("Selected.TButton",
        background=[("active", "#005cb2")])

    app = CCTVApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)  # 🛑 safe app close
    root.mainloop()