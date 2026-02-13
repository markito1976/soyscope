@echo off
title SoyScope - Industrial Soy Research Dashboard
cd /d "%~dp0"
python -c "from soyscope.gui.main_window import launch_gui; launch_gui()"
pause
