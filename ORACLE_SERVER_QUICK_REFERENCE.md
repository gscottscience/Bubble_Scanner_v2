#### After Uploading or Syncing Files

1. SSH into your Oracle server:
  ```
  ssh -i "/Users/gscott/Library/CloudStorage/GoogleDrive-gscott@andrews.esc18.net/My Drive/#UIL/bubble_scanner_v2_web/ssh-key-2025-10-23.key" ubuntu@129.146.91.68
  ```
2. Go to your project directory (if needed):
  ```
  cd ~/bubble_scanner_v2_web
  ```
3. Restart your app’s service to apply the updates:
  ```
  sudo systemctl restart bubble-scanner.service
  ```
4. Open your app in the browser and verify the new features are working.
### Faster Updates with rsync

Instead of copying the entire folder every time, use `rsync` to sync only changed files:

```
rsync -avz \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '.DS_Store' \
  --exclude 'Test Scans/' \
  --exclude 'Terminal outputs/' \
  -e "ssh -i '/Users/gscott/Library/CloudStorage/GoogleDrive-gscott@andrews.esc18.net/My Drive/#UIL/bubble_scanner_v2_web/ssh-key-2025-10-23.key'" \
  ./bubble_scanner_v2_web/ ubuntu@129.146.91.68:~/bubble_scanner_v2_web/
```

This will only transfer new or modified files and skip unnecessary folders, making updates much faster.
## 8. Update the App with New Code

To deploy new changes from your local machine to the Oracle server:

1. Open a terminal on your local machine.
2. Use `scp` to copy the updated files or folders to the server. For example:

```
scp -i "/Users/gscott/Library/CloudStorage/GoogleDrive-gscott@andrews.esc18.net/My Drive/#UIL/bubble_scanner_v2_web/ssh-key-2025-10-23.key" -r "/Users/gscott/Library/CloudStorage/GoogleDrive-gscott@andrews.esc18.net/My Drive/#UIL/bubble_scanner_v2_web" ubuntu@129.146.91.68:~/
```

3. SSH into the server:
```
ssh -i "/Users/gscott/Library/CloudStorage/GoogleDrive-gscott@andrews.esc18.net/My Drive/#UIL/bubble_scanner_v2_web/ssh-key-2025-10-23.key" ubuntu@129.146.91.68
```

4. Go to the project directory (if needed):
```
cd ~/bubble_scanner_v2_web
```

5. Restart the app service:
```
sudo systemctl restart bubble-scanner.service
```

Your changes will now be live!
# Oracle Cloud Bubble Scanner Server: Quick Reference
login gscottscience
pw: Bubblescan#1

## 1. SSH into Your Server

Open your terminal and run:

```
ssh -i "/Users/gscott/Library/CloudStorage/GoogleDrive-gscott@andrews.esc18.net/My Drive/#UIL/bubble_scanner_v2_web/ssh-key-2025-10-23.key" ubuntu@129.146.91.68
```
- Update the path if your key is elsewhere.
- Use your current server IP if it changes.

---

## 2. Check if the App is Running

```
sudo systemctl status bubble-scanner.service
```
- "active (running)" means your app is up.

---

## 3. Start or Restart the App

```
sudo systemctl restart bubble-scanner.service
```

---

## 4. Check/Reload nginx (Web Server)

Check nginx config:
```
sudo nginx -t
```
Reload nginx:
```
sudo systemctl reload nginx
```

---

## 5. After a Reboot

Your app and firewall rules start automatically. To check:
```
sudo systemctl status bubble-scanner.service
```

---

## 6. Access Your App

- In your browser, go to:  
  `https://129.146.91.68`
- Click "Advanced" and "Proceed" if you see a security warning (self-signed certificate).

---

## 7. Update Your Code

- Upload new files to the server (e.g., with `scp`)
- Restart the service:
```
sudo systemctl restart bubble-scanner.service
```

---

**Keep this file for future reference!**
