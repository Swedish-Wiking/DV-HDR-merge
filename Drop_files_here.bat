@echo off 
pushd %~dp0
python "DV_HDR_merge.py" %*
pause