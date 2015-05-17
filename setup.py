from cx_Freeze import setup, Executable
includes = ['C:\\Python34\\Settings.py', 'C:\\Python34\\Utils.py']
#c:\python34\python.exe setup.py build
setup( name = "PeerToPeer" , version = "0.1" , description = "This is a program to encode or decode message" , executables = [Executable("PeerToPeer.py",base = "Win32GUI")] , )