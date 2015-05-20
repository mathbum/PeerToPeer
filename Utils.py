import socket,os,Settings,winsound,re,datetime
PACKET_SIZE=1048576 #102400
SEND_FILE_HEADER = b'SDFL'
FILE_REQUEST = b'FILE'
MESSAGE_HEADER = b'MESS'
LIST_HEADER = b'LSRQ'
LIST_RES_HEADER = b'LSRS'
BEAT_HEADER = b'BEAT'
CONN_HEADER = b'CONN'
FILE_NOT_EXIST_ERR = b'FDNE'
DOWNLOADS_DIR = os.path.join(os.getcwd(),"downloads")
UPLOADS_DIR = os.path.join(os.getcwd(),"uploads")
RETRY_LIMIT=2

def bytesToInt(byteNum):
	return int.from_bytes(byteNum, byteorder='big')

def intToBytes(num,numofbytes):
	return num.to_bytes(numofbytes,byteorder='big')

def stringToBytes(string):
	return bytes(string,'utf-8')

def bytesToString(bytes):
	return bytes.decode('utf-8')

def join(path1,path2):
	return os.path.join(path1,path2)

def getPacketOrStop(sock,size,threads):
	value = getPacket(sock,size)
	if value==None:
		print("Sender Disconnected")
		for i in len(threads):
			threads[i].stop()
	else:
		return value

def getPacket(sock,size):
	stopTime=datetime.datetime.now() + datetime.timedelta(minutes=1)
	remainingsize=size
	data = sock.recv(remainingsize)
	while 1:
		if datetime.datetime.now()>stopTime:
			return None
		else:
			if len(data)==size:
				return data
			elif len(data)>0:
				remainingsize=size-len(data)
			data += sock.recv(remainingsize)
			stopTime=datetime.datetime.now() + datetime.timedelta(minutes=1)

def padMessage(message,desiredSize):
	for i in range(len(message),desiredSize):
		message=message+b'\x00'
	return message

def printSpeed(time,size):#abstract the conversion
# test with 2TB
	print(time)
	extensions = [" Bytes","KBs","MBs","GBs"]
	if time==0:
		print("Instant Transmission")
	elif size>0:
		i=0
		for i in range(0,4):
			if size>1024:
				size=size/1024
			else:
				break
		print(format(float(size)/time,'.2f'),end='')
		print(extensions[i]+" per seconds")

def getFilesToDownload(files,folderStruc):
	"""returns a list of unique files (and their size) given the folderstuct and list of files"""
	uniqueFiles=set()
	for i in range(0,len(files)):
		uniqueFiles.update(getFilesAndSubFilesHelper(files[i],folderStruc)) 
	return list(uniqueFiles)

def getFilesAndSubFilesHelper(fle,folderStruc):
	"""returns a set of files given the folderStruc and file"""
	files = set()
	for i in range(0,len(folderStruc)):
		files.update(getFilesAndSubFiles(fle,folderStruc[i]))
	return files

def getFilesAndSubFiles(fle,path):
	filesToDownload=set()
	if isinstance(path,list):
		foldername = path[0]
		addfolder = False
		if fle==True or fle==foldername:#add the whole folder
			addfolder=True
		for i in range(1,len(path)):
			val = None
			if addfolder:
				val = getFilesAndSubFiles(True,path[i])#True means add all files checked. it is used for folder downloads
			else:
				val = getFilesAndSubFiles(fle,path[i])
			if not(val==None):
				filesToDownload.update(val)
	else:
		if fle==True or fle==path[0]:
			filesToDownload.add(path)
	return filesToDownload

def mergeSort(alist):#in place mergesort
	if len(alist)>1:
		mid = len(alist)//2
		lefthalf = alist[:mid]
		righthalf = alist[mid:]

		mergeSort(lefthalf)
		mergeSort(righthalf)

		i=0
		j=0
		k=0
		while i<len(lefthalf) and j<len(righthalf):
			if lessThan(lefthalf[i][1],righthalf[j][1]):
				alist[k]=lefthalf[i]
				i=i+1
			else:
				alist[k]=righthalf[j]
				j=j+1
			k=k+1

		while i<len(lefthalf):
			alist[k]=lefthalf[i]
			i=i+1
			k=k+1

		while j<len(righthalf):
			alist[k]=righthalf[j]
			j=j+1
			k=k+1

def lessThan(str1,str2):
	isless = False
	length = len(str2)
	if len(str1)<len(str2):
		isless = True
		length=len(str1)
	for i in range(0,length):
		if str1[i]<str2[i]:
			isless=True
			break
		elif str1[i]>str2[i]:
			isless=False
			break
	return isless

def sort(lst):#return sorted list
	conlist = convertList(lst)
	mergeSort(conlist)
	sortedList=[]
	for i in range(0,len(conlist)):
		sortedList.append(conlist[i][0])
	return sortedList

def convertList(lst):#take a list of strings a return a list of (string,[modified char values])
	newlst=[]
	for i in range(0,len(lst)):
		nums = []
		for j in range(0,len(lst[i])):
			nums.append(charToInt(lst[i][j]))
		newlst.append((lst[i],nums))
	return newlst


def charToInt(char):#make special chars be ascii value, digits be 128-136 and character be next
	if char.isdigit():
		return ord(char)+79
	elif char.isalpha():
		return ord(char.lower())+40
	else:
		return ord(char)



def listfolder(folderpath):
	"""Lists files and folders and their associated size"""
	files = os.listdir(folderpath)
	folder=[]
	orderedfiles=[]
	tempfileslist=[]
	totalsize = 0
	for i in range(0,len(files)):#put folders first
		fullname = os.path.join(folderpath,files[i])
		if os.path.isdir(fullname):
			orderedfiles.append(files[i])
		else:
			if files[i]!="desktop.ini":#remove the common protected file desktop.ini
				tempfileslist.append(files[i])

	orderedfiles = sort(orderedfiles)
	tempfileslist = sort(tempfileslist)
	orderedfiles.extend(tempfileslist)

	for i in range(0,len(orderedfiles)):
		fullname = os.path.join(folderpath,orderedfiles[i])
		if os.path.isdir(fullname):
			fldstruc,size = listfolder(fullname)
			folder.append([(orderedfiles[i],size),fldstruc])
			totalsize+=size
		else:
			size = os.path.getsize(fullname)
			folder.append((orderedfiles[i],size))
			totalsize+=size
	return folder,totalsize

def getSettings():
	Settings.clean()
	Settings.writemissing()
	settings = Settings.loadsettings()
	print(settings)
	return settings[0],settings[1],settings[2],settings[3],settings[4]

def playGotMessageSound():
	soundfile = os.getcwd()+"//test.wav"
	winsound.PlaySound(soundfile,winsound.SND_FILENAME|winsound.SND_ASYNC)