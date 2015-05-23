import os,sys,copy,re

settingsFile = os.getcwd()+"\Connections.Strider"

def isValidRandomValue(userName):
	if isinstance(userName, str) and not(";" in userName):
		return True
	else:
		return False

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

validityCheck = [isValidRandomValue,isValidIP,isValidRandomValue]

def getConnections():
	clean()
	return loadsettings()

def filterstring(str):
	str = re.findall("[ -~\n]",str)
	return ''.join(str)

def loadsettings():
	if not os.path.exists(settingsFile):
		f = open(settingsFile, "w")
		f.close()
		return []
	with open(settingsFile) as f:
		try:
			string=filterstring(f.read().strip())
			settings = parsesettings(string.split('\n'))
		except:
			return [] 
	f.close()
	return settings

def parsesettings(settingsarray):
	settings=[]
	for setting in settingsarray:
		splitsetting=setting.split(";")
		key=splitsetting[0].strip()
		ip=splitsetting[1].strip()
		name = splitsetting[2].strip()
		settings.append([key,ip,name])
	return settings

def loadfile():
	f = open(settingsFile,"r")
	string=f.read()
	string=string.strip()
	settings = filterstring(string).split('\n')
	return settings

def clean():
	if (not (os.path.exists(settingsFile))):
		f = open(settingsFile, "w")
		f.close()
	else:
		settings=[]
		settingsarray = loadfile()
		for line in settingsarray:
			splitsettings=line.split(";")
			if len(splitsettings)!=len(validityCheck):
				continue
			isValid = True
			for i in range(0,len(validityCheck)):
				isValid = isValid and validityCheck[i](splitsettings[i])
			if isValid:
				settings.append(line)
		settingsString=""

		for setting in settings:
			settingsString+=setting
			settingsString+="\n"

		settingsString=settingsString[:-1]

		f = open(settingsFile, "w")
		f.write(settingsString)
		f.close()