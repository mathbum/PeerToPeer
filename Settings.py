import os,sys,copy,re

MAX_UPORDOWN_THREADS = 100
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

def isValidIP(IP):
	if IP == "localhost":
		return True
	try: 
		IP = IP.split('.')
		for i in range(0,4):
			num = int(IP[i])
			if num<0 or num>255:
				return False
	except:
		return False
	return True

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

settingtitles=["Peer IP","Peer Port","Listening Port","Max Parallel Uploads","Max Parallel Downloads"]
defaultsettings = ["127.0.0.1",5005,5005,5,5]
validitycheck = [isValidIP,isValidPort,isValidPort,isValidInt,isValidInt]

file = os.getcwd()+"\Settings.txt"

def writedefaultsettings():
	stringToWrite=""
	f = open(file, "w")
	for i in range(0,len(defaultsettings)):
		stringToWrite += settingtitles[i]+"="+str(defaultsettings[i])+",\n"
	stringToWrite = stringToWrite[:-2]
	f.write(stringToWrite)
	f.close()

def filterstring(str):
	str = re.findall("[ -~]",str)
	return ''.join(str)

def loadsettings():
	if not os.path.exists(file):#short circuit the rest?
		writedefaultsettings()
	with open(file) as f:
		try:
			string=filterstring(f.read().strip())
			settings = parsesettings(string.split(','))
		except: 
			writedefaultsettings()
			settings=loadsettings()#make sure infinite isn't possible
	f.close()
	return settings

def parsesettings(settingsarray):
	settings=[]
	for i in range(0,len(defaultsettings)):
		settings.append("")
	for setting in settingsarray:
		splitsetting=setting.split("=")
		settitle=splitsetting[0].strip()
		setval=splitsetting[1].strip()
		if(settingtitles[0] == splitsetting[0]):
			settings[0]=setval
		elif(settingtitles[1] == splitsetting[0]):
			settings[1]=int(setval)
		elif(settingtitles[2] == splitsetting[0]):
			settings[2]=int(setval)
		elif(settingtitles[3] == splitsetting[0]):
			settings[3]=int(setval)
		elif(settingtitles[4] == splitsetting[0]):
			settings[4]=int(setval)
	return settings

def loadfile():
	f = open(file,"r")
	string=f.read()
	string=string.strip()
	settings = filterstring(string).split(',')
	return settings

def writesettingsfromstring(string,char):
	f = open(file,char) 
	f.write(string)
	f.close()

def clean():
	if (not (os.path.exists(file))):
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