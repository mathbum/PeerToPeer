import os,sys,copy,re

MAX_UPORDOWN_THREADS = 100
settingsFile = os.getcwd()+"\Settings.txt"
# def isvalidbool(boolean):
# 	boolean=str(boolean)
	# return boolean.lower() in ("yes","true","1","no","false","0")

# def stringtobool(string):
# 	string=str(string)
# 	return string.lower() in ("yes","true","1")

# def changesetting(settingtitle,currentsetting):
# 	settingsarray = loadfile()
# 	settingstring=""
# 	found=False
# 	for setting in settingsarray:
# 		if(setting.split('=')[0]==settingtitle):
# 			setting=settingtitle+'='+currentsetting
# 			found=True
# 		settingstring+=setting+",\n"
# 	if(not(found)):
# 		settingstring+=settingtitle+"="+currentsetting+",\n"
# 	writesettingsfromstring(settingstring[:-2],"w")

def isValidUserName(userName):
	if isinstance(userName, str) and not(";" in userName):
		return True
	else:
		return False

def isValidPort(port):
	try:
		port = int(port)
		if port>=1025 and port<=65535:
			return True
		else:
			return False
	except:
		return False

def isValidInt(num):
	try:
		num = int(num)
		if num>0 and num<=MAX_UPORDOWN_THREADS:
			return True
	except:
		return False
	return False
	
def isValidRandomValue(userName):
	if isinstance(userName, str) and not(";" in userName):
		return True
	else:
		return False


settingtitles=["Username","Listening Port","Peer Port","Max Parallel Uploads","Max Parallel Downloads", "SecretKey"]
defaultsettings = ["New User",5005,5005,5,5, "94k+=ey"] #default key needs to be random
validitycheck = [isValidUserName,isValidPort,isValidPort,isValidInt,isValidInt, isValidRandomValue]
converter = [str,int,int,int,int, str]

def writedefaultsettings():
	stringToWrite=""
	f = open(settingsFile, "w")
	for i in range(0,len(defaultsettings)):
		stringToWrite += settingtitles[i]+"="+str(defaultsettings[i])+",\n"
	stringToWrite = stringToWrite[:-2]
	f.write(stringToWrite)
	f.close()

def filterstring(str):
	str = re.findall("[ -~]",str)
	return ''.join(str)

def loadsettings():
	if not os.path.exists(settingsFile):#short circuit the rest?
		writedefaultsettings()
	with open(settingsFile) as f:
		try:
			string=filterstring(f.read().strip())
			settings = parsesettings(string.split(','))
		except: 
			writedefaultsettings()
			settings=loadsettings()
	f.close()
	return settings

def parsesettings(settingsarray):
	settings=[]
	for i in range(0,len(defaultsettings)):
		settings.append("")
	for setting in settingsarray:
		splitsetting=setting.split("=",1)
		settitle=splitsetting[0].strip()
		setval=splitsetting[1].strip()

		for i in range(0,len(settingtitles)):
			if settingtitles[i]==splitsetting[0]:
				settings[i]=converter[i](setval)
				break
	return settings

def loadfile():
	f = open(settingsFile,"r")
	string=f.read()
	string=string.strip()
	settings = filterstring(string).split(',')
	return settings

def writesettingsfromstring(string,char):
	f = open(settingsFile,char) 
	f.write(string)
	f.close()

def clean():
	if (not (os.path.exists(settingsFile))):
		writedefaultsettings()
	else:
		titles=copy.copy(settingtitles)
		settingsarray = loadfile()
		customtitle=titles[len(titles)-1]
		settingstring=""
		for setting in settingsarray:
			title=setting.split('=',1)[0].strip()
			if(title in titles):
				i=settingtitles.index(title)
				validfunction=validitycheck[i]
			else:
				continue
			if(validfunction(setting.split('=',1)[1].strip())):
				settingstring+=setting+",\n"
				titles.remove(title)
		settingstring=settingstring[:-2]
		if (not(filterstring(settingstring).split(',')==settingsarray)):
			writesettingsfromstring(settingstring,"w")

def writemissing():
	settingsarray=loadfile()
	missingtitles=copy.copy(settingtitles)
	for setting in settingsarray:
		title=setting.split('=')[0].strip()
		if(title in settingtitles):
			missingtitles.remove(title)
	stringtowrite=",\n"
	for i in range(0,len(settingtitles)):
		title=settingtitles[i]
		if(title in missingtitles):
			stringtowrite+=title+"="+str(defaultsettings[i])+",\n"
	if(len(stringtowrite)>2):
		stringtowrite=stringtowrite[:-2]
		writesettingsfromstring(stringtowrite,"a")