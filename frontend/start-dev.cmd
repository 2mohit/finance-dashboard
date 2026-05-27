@echo off
set PATH=C:\Program Files\nodejs;%PATH%
cd /d "D:\18_Claude_Code_Projects\01 Finance Dashboard\frontend"
"C:\Program Files\nodejs\node.exe" node_modules\.bin\vite --port 5175 --strictPort
