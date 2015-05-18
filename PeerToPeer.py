#!python3
import os,socket,inspect,ctypes,threading,queue,time,math,pickle
import Utils
from tkinter import *
from tkinter import ttk

TCP_IP = '127.0.0.1'
LISTENING_PORT=5005
TCP_PORT=5005
PACKET_SIZE=1048576 #102400
MAX_UPLOAD_THREADS=5
MAX_DOWNLOAD_THREADS=5
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
DOWNLOADS_MANAGER=None
UPLOADS_MANAGER=None
RETRY_LIMIT=2

def _async_raise(tid, exctype):
	"""raises the exception, performs cleanup if needed"""
	if not inspect.isclass(exctype):
		exctype = type(exctype)
	res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
	if res == 0:
		raise ValueError("invalid thread id")
	elif res != 1:
		"""if it returns a number greater than one, you're in trouble, 
		and you should call it again with exc=NULL to revert the effect"""
		ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
		raise SystemError("PyThreadState_SetAsyncExc failed")

class StoppableThread(threading.Thread):
	def stop(self):
		_async_raise(self.ident, SystemExit)

class ClientThread(StoppableThread):#responsible for sending messages to peer
	folderStruc=None
	def __init__(self,sock):
		threading.Thread.__init__(self)
		self.sock=sock
		self.mailBox=queue.Queue()

	def setFolderStruc(self,folderStruc):
		self.folderStruc=folderStruc

	def run(self):
		self.sock.send(LIST_HEADER)
		while 1:
			try:
				message = self.mailBox.get(timeout=15)
				messageType = message[0]
				if messageType=="MESSAGE":
					message=message[1]
					self.sendMessage(message)
				elif messageType=="FILES":
					selections = message[1]
					files = Utils.getFilesToDownload(selections,self.folderStruc)
					print(files)
					for i in range(0,len(files)):
						DOWNLOADS_MANAGER.mailBox.put(("FILES",[self.sock,files[i],RETRY_LIMIT]))
			except:
				self.sock.send(BEAT_HEADER)

	def sendMessage(self,message):
		size = 0
		maxMessageSize = PACKET_SIZE-8
		while(1):
			size = len(message)
			if size == 0:
				break
			elif size > maxMessageSize:
				size = maxMessageSize
			else:
				size = len(message)
			self.sock.send(MESSAGE_HEADER+Utils.intToBytes(size,4)+Utils.stringToBytes(message[:size]))
			message = message[size:]

class ServerThread(StoppableThread):
	def __init__(self,sock,chatLog,managerMailbox,client,browseTree,ip):
		threading.Thread.__init__(self)
		self.sock=sock
		self.chatLog=chatLog
		self.managerMailbox=managerMailbox
		self.client=client
		self.browseTree=browseTree
		self.ip = ip

	def run(self):
		while 1:
			control = Utils.getPacketOrStop(self.sock,4,self)
			print(control)
			if control == FILE_REQUEST:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,2,self))
				fileName = Utils.bytesToString(Utils.getPacketOrStop(self.sock,size,self))
				port = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,2,self))
				print("ip to send to"+self.ip)
				self.managerMailbox.put(("FILE",[self.ip,port,fileName]))
			elif control == MESSAGE_HEADER:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,4,self))
				data = Utils.bytesToString(Utils.getPacketOrStop(self.sock,size,self))
				# print(data)
				self.putOtherMessageInChat(data)
			elif control == LIST_HEADER:
				folderStruc = Utils.listfolder(UPLOADS_DIR)[0]
				encodedStruc = pickle.dumps(folderStruc)
				size = len(encodedStruc)
				self.sock.send(LIST_RES_HEADER+Utils.intToBytes(size,4)+encodedStruc)
			elif control == LIST_RES_HEADER:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,4,self))
				folderStruc = pickle.loads(Utils.getPacketOrStop(self.sock,size,self))
				strippedStruc = self.fillTreeWithFolder(self.browseTree,"",folderStruc,"")
				self.client.setFolderStruc(strippedStruc)
				# self.client.setFolderStruc(folderStruc)
			elif control==BEAT_HEADER:
				pass

	def putOtherMessageInChat(self,message):
		self.chatLog.config(state=NORMAL)
		if self.chatLog.index('end') != None:#whaat is this?
			# try:#why is there a try catch around this?
			LineNumber = float(self.chatLog.index('end'))-1.0
			# except:
				# pass
			self.chatLog.insert(END, "Other: " + message)
			self.chatLog.tag_add("Other", LineNumber, LineNumber+0.6)
			self.chatLog.tag_config("Other", foreground="#04B404", font=("Arial", 12, "bold"))
			self.chatLog.config(state=DISABLED)
			self.chatLog.yview(END)
			Utils.playGotMessageSound()

	def fillTreeWithFolder(self,tree,root,filestruc,path):
		"""Returns folderstruc without folder sizes"""
		folder = []
		for i in range(0,len(filestruc)):
			item = filestruc[i]
			if isinstance(item,list):#if its a folder
				itempath = Utils.join(path,item[0][0])
				direc = tree.insert(root,END,itempath,text=item[0][0],values=(item[0][1],""))
				prevfold=self.fillTreeWithFolder(tree,direc,item[1],itempath)
				prevfold.insert(0,itempath)
				folder.append(prevfold)
			else:#if its a file
				fileext = os.path.splitext(item[0])[1]
				folder.append((Utils.join(path,item[0]),item[1]))
				tree.insert(root,END,Utils.join(path,item[0]),text=item[0],values=(item[1],fileext))
		return folder

class ListeningThread(StoppableThread):
	chatLog = None
	browseTree=None

	def setChatLog(self,chatLog):
		self.chatLog=chatLog

	def setBrowseTree(self,browseTree):
		self.browseTree=browseTree

	def run(self):
		try:#start off by trying to connect to other peer
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((TCP_IP, TCP_PORT))
			self.connectToPeer(s,TCP_IP)
		except:
			pass
		s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s1.bind(('',LISTENING_PORT))
		s1.listen(1)# number of backloged connections
		while 1:
			s2, addr = s1.accept()
			print('Connection address: '+str(addr))
			self.connectToPeer(s2,addr[0])

	def connectToPeer(self,sock,addressIP):
		client = ClientThread(sock)
		server = ServerThread(sock,self.chatLog,UPLOADS_MANAGER.mailBox,client,self.browseTree,addressIP)
		client.start()
		server.start()
		connections.append((sock,server,client))

class IndDownloadThread(StoppableThread):#change stop function to notify the manager
	fullFilePath=None#filepath to the client
	fle=None#actual file object
	isCancelled = False
	def __init__(self,sock,filePath,mailbox,downloadTree,treeItem):
		threading.Thread.__init__(self)
		self.sock = sock
		self.filePath=filePath#filepath to the server and download manager
		self.managerMailbox=mailbox
		self.treeItem = treeItem
		self.downloadTree=downloadTree

	def setCancelled(self,isCancelled):
		self.isCancelled=isCancelled

	def run(self):
		self.requestFile()

	def recieveFile(self,sock,size):
		self.fullFilePath = Utils.join(DOWNLOADS_DIR,self.filePath)
		directory = os.path.dirname(self.fullFilePath)
		if not os.path.exists(directory):
			os.makedirs(directory)
		remainingsize=size
		f = open(self.fullFilePath,'wb')
		self.fle=f
		count=0
		while(1):
			if remainingsize==0:
				break
			elif remainingsize>=PACKET_SIZE:
				packet = Utils.getPacketOrStop(sock,PACKET_SIZE,self)
				remainingsize = remainingsize-PACKET_SIZE
				if count%10==0:
					percent = format(float(size-remainingsize)/float(size)*100,'.2f')
					self.downloadTree.set(self.treeItem,"progress",str(percent)+"%")#make this happen not as often
				count+=1
			else:
				packet = Utils.getPacketOrStop(sock,remainingsize,self)
				remainingsize=0
			f.write(packet)
		f.close()

	def requestFile(self):
		conn = None
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.bind((self.sock.getsockname()[0],0))
			s.listen(1)
			message = FILE_REQUEST+Utils.intToBytes(len(self.filePath),2)+Utils.stringToBytes(self.filePath)+Utils.intToBytes(s.getsockname()[1],2)#need to also send ip address
			self.sock.send(message)
			conn,addr = s.accept()
			succ = True
			rec = Utils.getPacketOrStop(conn,9,self)
			control = rec[:4]
			if control==SEND_FILE_HEADER:
				size = Utils.bytesToInt(rec[5:])
				self.recieveFile(conn,size)
			elif control == FILE_NOT_EXIST_ERR:
				print("The Requested File Isn't Being Uploaded By The Peer")
				succ = False
			else:
				print("There Was An Error With The Specified File")
				succ = False
			conn.close()
			if succ:
				self.downloadTree.set(self.treeItem,"progress","Done")
				self.downloadTree.move(self.treeItem,'',0)
			else:
				self.downloadTree.set(self.treeItem,"progress","failed")
			self.managerMailbox.put(("THREAD",(self,self.filePath,succ,self.treeItem)))
		except SystemExit:#stopped by another thread
			if conn!=None:
				conn.close()
			if self.fle!=None:
				self.fle.close()
				os.remove(self.fullFilePath)
			self.managerMailbox.put(("THREAD",(self,self.filePath,self.isCancelled,self.treeItem)))
		except:
			print("caught")
			self.downloadTree.set(self.treeItem,"progress","failed")
			print(self.filePath)
			self.managerMailbox.put(("THREAD",(self,self.filePath,False,self.treeItem)))

class DownloadManagerThread(StoppableThread):#if thread downloads thread crashs make it auto retry
	downloadList=[]#(sock,filename,retries,treeItem)
	folderStruc = None
	downloadTree = None

	def __init__(self):
		threading.Thread.__init__(self)
		self.mailBox=queue.Queue()

	def setTree(self,downloadTree):
		self.downloadTree=downloadTree

	def appendFiles(self,downloadInfo):#[sock,file,retries]
		self.downloadTree.insert("",END,text=downloadInfo[1][0],values=(downloadInfo[0].getsockname(),downloadInfo[1][1],"Waiting"))
		children = self.downloadTree.get_children('')
		downloadInfo.append(children[len(children)-1])
		self.downloadList.append(tuple(downloadInfo))#abstract this up
		for i in range(len(downloadThreads),MAX_DOWNLOAD_THREADS):
			self.downloadNext()

	def downloadNext(self):
		if len(downloadThreads)<MAX_DOWNLOAD_THREADS and len(self.downloadList)>0:
			nextDownloadInfo = self.downloadList.pop(0)
			sock = nextDownloadInfo[0]
			nextFile=nextDownloadInfo[1][0]
			retries=nextDownloadInfo[2]
			treeItem = nextDownloadInfo[3]
			print("going to download "+nextFile)
			t = IndDownloadThread(sock,nextFile,self.mailBox,self.downloadTree,treeItem)
			downloadThreads.append((t,nextFile,retries))
			t.start()

	def removeThread(self,itemToRemove):
		try:#in case the thread is no longer in the downloadThreads list
			downloadThreads.remove(itemToRemove)
		except:
			pass
		self.downloadNext()
	
	def run(self):
		while(1):
			data = self.mailBox.get()
			messageType = data[0]
			data = data[1]
			if messageType == "THREAD":#if its a thread claiming it is done (thread,filepath,succ,treeItem)
				print("download thread returned: "+str(data[2]))
				listItem = None
				for i in range(0,len(downloadThreads)):
					if data[0]==downloadThreads[i][0]:
						listItem=downloadThreads[i]
						break
				print(data)
				if not(data[2]):#unsucessful download
					retries = listItem[2]-1
					if retries>0:
						self.downloadList.insert(0,(data[0].sock,(data[1],-1),retries,data[3]))
						self.downloadTree.set(data[3],"progress","waiting")
				self.removeThread(listItem)
			elif messageType=="CANCEL":
				for i in range(0,len(data)):
					self.cancelDownload(data[i])
			elif messageType == "FILES":#if its a new files to download format (sock,file,retrylimit)
				self.appendFiles(data)
			else:
				print("download manager got unknown mail: ")
				print(messageType)

	def cancelDownload(self,itemName):
		handled = False
		item = self.downloadTree.item(itemName)
		progress = item["values"][2]
		if progress == "Done":
			return

		itemToRemove = None
		for i in range(0,len(self.downloadList)):#remove from list waiting to download
			if self.downloadList[i][3]==itemName:
				self.downloadTree.set(itemName,"progress","Canceled")
				itemToRemove=i
				handled=True
				break

		if not(handled):
			for i in range(0,len(downloadThreads)):#remove from current downloads
				threadInfo = downloadThreads[i]
				thread = threadInfo[0]
				if thread.treeItem==itemName:
					thread.setCancelled(True)
					thread.stop()
					self.downloadTree.set(itemName,"progress","Canceled")
					handled=True
					break
		else:
			self.downloadList.pop(itemToRemove)

		if not(handled):#remove from completed download that was canceled before it completed
			os.remove(Utils.join(DOWNLOADS_DIR,item["text"]))
			self.downloadTree.set(itemName,"progress","Canceled")

class IndUploadThread(StoppableThread):#change stop function to notify the manager
	fle=None#actual file object

	def __init__(self,sock,filePath,mailbox,uploadTree,treeItem):
		threading.Thread.__init__(self)
		self.sock = sock
		self.filePath=filePath#filepath to the server and upload manager
		self.managerMailbox=mailbox
		self.uploadTree = uploadTree
		self.treeItem=treeItem

	def run(self):
		self.sendFile()

	def sendFileInfo(self,filename):
		message=""
		size=None
		numofpacks=None
		try:
			size = os.path.getsize(filename)
			numofpacks = math.ceil(size/PACKET_SIZE)
			message = SEND_FILE_HEADER+Utils.intToBytes(size,5)

		except:
			print("FILE DOESN'T EXIST")
			self.uploadTree.set(self.treeItem,"progress","DNE")
			message=Utils.padMessage(FILE_NOT_EXIST_ERR,9)
		self.sock.send(message)
		return size,numofpacks

	def sendFile(self):# tell server user that you are sending and it is sent
		try:
			fullfilename = Utils.join(UPLOADS_DIR,self.filePath)
			print("fullfilename: "+fullfilename)
			size,numofpacks=self.sendFileInfo(fullfilename)

			if size==None:
				self.managerMailbox.put(("THREAD",(self,self.filePath)))
				self.sock.close()
				return

			t0 = time.time()
			with open(fullfilename, 'rb') as f:
				self.fle=f
				for i in range(1,numofpacks+1):
					data = f.read(PACKET_SIZE)
					percent = format(float(i)/float(numofpacks)*100,'.2f')
					self.uploadTree.set(self.treeItem,"progress",str(percent)+"%")#make this happen not as often
					self.sock.send(data)
			t1 = time.time()
			Utils.printSpeed(t1-t0,size)
			f.close()
			self.uploadTree.set(self.treeItem,"progress","Done")
			self.managerMailbox.put(("THREAD",(self,self.filePath)))
			self.sock.close()
		except SystemExit:
			if self.sock!=None:
				# self.sock.close()
				self.sock.shutdown(socket.SHUT_RDWR)
				self.sock.close()
			if self.fle!=None:
				self.fle.close()
			self.managerMailbox.put(("THREAD",(self,self.filePath)))
		except:
			# print(sys.exc_info()[0])
			self.uploadTree.set(self.treeItem,"progress","Failed")
			self.managerMailbox.put(("THREAD",(self,self.filePath)))

class UploadManagerThread(StoppableThread):
	uploadList=[]#(ip,port,filename,treeItem)

	def __init__(self):
		threading.Thread.__init__(self)
		self.mailBox=queue.Queue()

	def setTree(self,uploadTree):
		self.uploadTree=uploadTree

	def appendFile(self,uploadInfo):# [sockname,port,filename]
		size = 0
		try:
			size = os.path.getsize(Utils.join(UPLOADS_DIR,uploadInfo[2]))
		except:
			pass
		self.uploadTree.insert("",END,text=uploadInfo[2],values=(str(uploadInfo[0])+" "+str(uploadInfo[1]),size,"Waiting"))
		children = self.uploadTree.get_children('')
		uploadInfo.append(children[len(children)-1])
		self.uploadList.append(tuple(uploadInfo))#abstract this up

		for i in range(len(uploadThreads),MAX_UPLOAD_THREADS):
			self.uploadNext()

	def uploadNext(self):
		if len(uploadThreads)<MAX_UPLOAD_THREADS and len(self.uploadList)>0:      
			nextFileInfo = self.uploadList.pop(0)
			ip = nextFileInfo[0]
			port = nextFileInfo[1]
			nextFile=nextFileInfo[2]
			treeItem = nextFileInfo[3]
			print("going to upload "+nextFile)

			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((ip, port))
			print("connected: "+str(ip)+" "+str(port))

			t = IndUploadThread(s,nextFile,self.mailBox,self.uploadTree,treeItem)
			uploadThreads.append((t,nextFile))
			t.start()

	def removeThread(self,itemToRemove):
		uploadThreads.remove(itemToRemove)
		self.uploadNext()
	
	def run(self):
		while(1):
			data = self.mailBox.get()
			messageType = data[0]
			data = data[1]
			if messageType == "THREAD":#isinstance(data[0],StoppableThread):#i don't think we need the filename
				print("Upload thread returned")
				self.removeThread(data)
			elif messageType=="CANCEL":
				for i in range(0,len(data)):
					self.cancelUpload(data[i])
			elif messageType=="FILE":#if its a new file to upload [ip,port,filename]
				self.appendFile(data)

	def cancelUpload(self,itemName):
		handled = False
		item = self.uploadTree.item(itemName)
		progress = item["values"][2]
		if progress == "Done":
			return

		itemToRemove = None
		for i in range(0,len(self.uploadList)):#remove from list waiting to upload
			if self.uploadList[i][3]==itemName:
				self.uploadTree.set(itemName,"progress","Canceled")
				itemToRemove = i
				handled=True
				break

		if not(handled):
			for i in range(0,len(uploadThreads)):#remove from current uploads
				threadInfo = uploadThreads[i]
				thread = threadInfo[0]
				if thread.treeItem==itemName:
					thread.stop()
					self.uploadTree.set(itemName,"progress","Canceled")
					break
		else:
			self.uploadList.pop(itemToRemove)






def mainWindow(listeningThread):
	def SendMessageAction():
		message = EntryBox.get("0.0",END).strip()+"\n"
		if message!="\n": #empty message
			connections[0][2].mailBox.put(("MESSAGE",message))#send message to first person you connected to
			putMyMessageInChat(message)
			ChatLog.yview(END)
		EntryBox.delete("0.0",END)

	def putMyMessageInChat(message):
		ChatLog.config(state=NORMAL)
		if ChatLog.index('end') != None:
			LineNumber = float(ChatLog.index('end'))-1.0
			ChatLog.insert(END, "You: " + message)
			ChatLog.tag_add("You", LineNumber, LineNumber+.4)
			ChatLog.tag_config("You", foreground="#FF8000", font=("Arial", 12, "bold"))
			ChatLog.config(state=DISABLED)
			ChatLog.yview(END)

	def PressAction(event):
		EntryBox.config(state=NORMAL)
		SendMessageAction()

	def CancelDownload():
		selections = downloadTree.selection()
		DOWNLOADS_MANAGER.mailBox.put(("CANCEL",selections))

	def CancelUpload():
		selections = uploadTree.selection()
		print(selections)
		UPLOADS_MANAGER.mailBox.put(("CANCEL",selections))

	# def DisableEntry(event):
	#   EntryBox.config(state=DISABLED)

	def download():
		selections = browseTree.selection()
		# print(selections)
		# print(browseTree.item(selections[0]))
		connections[0][2].mailBox.put(("FILES",selections))#request file from first person you connected to

	master = Tk()

	tabs = ttk.Notebook(master)

	messageTab=Frame(master)
	browseTab=Frame(master)
	downloadsTab=Frame(master)
	uploadsTab=Frame(master)
	messF1=Frame(messageTab)
	messF2=Frame(messageTab)
	browseF1 = Frame(browseTab)
	browseF2 = Frame(browseTab)
	downloadF1 = Frame(downloadsTab)
	downloadF2 = Frame(downloadsTab)
	uploadF1 = Frame(uploadsTab)
	uploadF2 = Frame(uploadsTab)
	tabs.add(messageTab,text="Messaging",compound=TOP)
	tabs.add(browseTab,text="Browse",compound=TOP)
	tabs.add(downloadsTab,text="Downloads",compound=TOP)
	tabs.add(uploadsTab,text="Uploads",compound=TOP)
	tabs.pack(fill=BOTH, expand=True)

	browseScroll = Scrollbar(browseF1)
	browseTree = ttk.Treeview(browseF1,yscrollcommand=browseScroll.set)
	browseTree["columns"]=("size","type")
	browseTree.column("#0", width=500)
	browseTree.column("size", width=75)
	browseTree.column("type", width=40)
	browseTree.heading("#0",text="Name",anchor=W)
	browseTree.heading("type", text="Type",anchor=W) 
	browseTree.heading("size", text="Size",anchor=W)
	browseScroll.config(command=browseTree.yview)
	browseScroll.pack(side=RIGHT,fill=Y)
	browseTree.pack(expand=True,fill=BOTH)


	downloadButton = Button(browseF2,text="download",command=download)  
	downloadButton.pack()

	downloadScroll = Scrollbar(downloadF1)
	downloadTree = ttk.Treeview(downloadF1,yscrollcommand=downloadScroll.set)
	downloadTree["columns"]=("host","size","progress")
	downloadTree.column("#0", width=400)
	downloadTree.column("host",width=100)
	downloadTree.column("size", width=75)
	downloadTree.column("progress",width=75)
	downloadTree.heading("#0",text="Name",anchor=W)
	downloadTree.heading("size", text="Size",anchor=W)
	downloadTree.heading("host", text="Host",anchor=W)
	downloadTree.heading("progress", text="Progress",anchor=W)
	downloadScroll.config(command=downloadTree.yview)
	downloadScroll.pack(side=RIGHT,fill=Y)
	downloadTree.pack(fill=BOTH, expand=True)

	DOWNLOADS_MANAGER.setTree(downloadTree)
	DOWNLOADS_MANAGER.start()

	downloadCancelB = Button(downloadF2,text="cancel",command=CancelDownload)
	downloadCancelB.pack()

	browseF1.pack(fill=BOTH, expand=True)
	browseF2.pack()
	downloadF1.pack(fill=BOTH, expand=True)
	downloadF2.pack()



	ChatLog = Text(messF1, bd=0, bg="white", height="8", width="50", font="Arial")
	ChatLog.config(state=DISABLED)

	scrollbar = Scrollbar(messF1, command=ChatLog.yview)#, cursor="heart")
	ChatLog['yscrollcommand'] = scrollbar.set

	SendButton = Button(messF2, font=30, text="Send", width="12", height=5, bd=0, bg="#FFBF00", activebackground="#FACC2E",command=SendMessageAction)

	EntryBox = Text(messF2, bd=0, bg="white",width="29", height="5", font="Arial")
	# EntryBox.bind("<Return>", DisableEntry)
	EntryBox.bind("<KeyRelease-Return>", PressAction)

	scrollbar.pack(side=RIGHT,fill=Y,pady=(5,5))
	ChatLog.pack(pady=(5,5),fill=BOTH, expand=True)
	SendButton.pack(side=RIGHT,pady=(0,5))
	EntryBox.pack(pady=(0,5),fill=BOTH, expand=True)

	messF1.pack(fill=BOTH, expand=True)
	messF2.pack(fill=BOTH, expand=True)

	# r1 = browseTree.insert("",END,text="filename",values=("host","size","progress"))
	# browseTree.insert(r1,END,text="vale1",values=("val2","size","progress"))

	# children = downloadTree.get_children("")
	# print(children)
	# downloadTree.set(children[1],"size","newvalue")
	# print(downloadTree.item(children[1]))
	# print(downloadTree.item(children[1])["text"])
	# print(downloadTree.identify_row(1))


	uploadScroll = Scrollbar(uploadF1)
	uploadTree = ttk.Treeview(uploadF1,yscrollcommand=uploadScroll.set)
	uploadTree["columns"]=("client","size","progress")
	uploadTree.column("#0", width=400)
	uploadTree.column("client",width=100)
	uploadTree.column("size", width=75)
	uploadTree.column("progress",width=75)
	uploadTree.heading("#0",text="Name",anchor=W)
	uploadTree.heading("size", text="Size",anchor=W)
	uploadTree.heading("client", text="Client",anchor=W)
	uploadTree.heading("progress", text="Progress",anchor=W)
	uploadScroll.config(command=uploadTree.yview)
	uploadScroll.pack(side=RIGHT,fill=Y)
	uploadTree.pack(fill=BOTH, expand=True)

	uploadCancelB= Button(uploadF2,text="cancel",command=CancelUpload)
	uploadCancelB.pack()

	browseF1.pack(fill=BOTH, expand=True)
	browseF2.pack()
	uploadF1.pack(fill=BOTH, expand=True)
	uploadF2.pack()

	UPLOADS_MANAGER.setTree(uploadTree)
	UPLOADS_MANAGER.start()

	listeningThread.setChatLog(ChatLog)
	listeningThread.setBrowseTree(browseTree)
	listeningThread.start()


	mainloop()

if (__name__ == "__main__"):
	TCP_IP,TCP_PORT,LISTENING_PORT,MAX_UPLOAD_THREADS,MAX_DOWNLOAD_THREADS = Utils.getSettings()
	# print(TCP_IP+", "+str(TCP_PORT))

	connections=[] #(socket,serverthread,clientthread)

	"""remove these. just managers should know about these"""
	uploadThreads = [] # (thread,filename)
	downloadThreads=[] # (thread,filename,retryamount) so that if a failed file. it can retry download

	listeningThread = ListeningThread()

	UPLOADS_MANAGER = UploadManagerThread()

	DOWNLOADS_MANAGER = DownloadManagerThread()
	
	mainWindow(listeningThread)

	#refactor
	#abstract up thread methods
	#move threads to seperate file
	#replace some of the lists with class objects to increase readability

	#make all threads close if gui closes
	#make getpacket not be an active wait
	#fix gui lag while downloading
	#set proper update rates for upload and downloads
	#allow dynamically add and delete files to their upload folders
	#if a download is 50% and request it again it starts at 50% not 0%
	#move canceled downloads below completed and above current
	#what if download same filename from different peers
	#make it so if a peer is full on uploads a requesting downloader doesn't wait all day
	#display max upload/downloads allow it to be changed but error check that its <= 100 and > 0
	#allow user to clear finished uploaded or downloaded files
	#put ip address instead of "Other" in chat
	#make distinction between system message,other messages and your own
	#what if gui is closed before all threads are finished?
	#maintain ip address
	#errors
	#add max up/download to screen, add clear, add cancel/cancell all, add clear completed checkbox
	#spawn new processes for fuller parallelism (downloader and uploader)
	#change the stop time in get packet so it only updates the time when you get new data, not every time
	#heart beat bug - if user downlaods something every 14 seconds, client never sends beat
	#make sure getpacketorstop ends both threads, not just server thread