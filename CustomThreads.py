import os,socket,inspect,ctypes,threading,queue,time,math,pickle
import Utils
from tkinter import *
from tkinter import ttk

class CancelException(SystemError):
  pass

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

class TransferThread(StoppableThread):
	fle=None#actual file object
	isCancelled = False
	def __init__(self,sock,filePath,mailbox,tree,treeItem):
		threading.Thread.__init__(self)
		self.sock = sock
		self.filePath=filePath#filepath to the server and download manager
		self.managerMailbox=mailbox		
		self.tree=tree
		self.treeItem = treeItem

	def setCancelled(self,isCancelled):
		self.isCancelled=isCancelled

class ClientThread(StoppableThread):#responsible for sending messages to peer
	folderStruc=None

	def __init__(self,sock,managerMailbox):
		threading.Thread.__init__(self)
		self.sock=sock
		self.mailBox=queue.Queue()
		self.managerMailbox = managerMailbox

	def setFolderStruc(self,folderStruc):
		self.folderStruc=folderStruc

	def run(self):
		self.sock.send(Utils.LIST_HEADER)
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
					self.sock.send(Utils.BEAT_HEADER)
					for i in range(0,len(files)):
						self.managerMailbox.put(("FILES",[self.sock,files[i],Utils.RETRY_LIMIT]))
			except:
				self.sock.send(Utils.BEAT_HEADER)

	def sendMessage(self,message):
		size = 0
		maxMessageSize = Utils.PACKET_SIZE-8
		while(1):
			size = len(message)
			if size == 0:
				break
			elif size > maxMessageSize:
				size = maxMessageSize
			else:
				size = len(message)
			self.sock.send(Utils.MESSAGE_HEADER+Utils.intToBytes(size,4)+Utils.stringToBytes(message[:size]))
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
			control = Utils.getPacketOrStop(self.sock,4,(self,self.client))
			print(control)
			if control == Utils.FILE_REQUEST:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,2,(self,self.client)))
				fileName = Utils.bytesToString(Utils.getPacketOrStop(self.sock,size,(self,self.client)))
				port = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,2,(self,self.client)))
				print("ip to send to"+self.ip)
				self.managerMailbox.put(("FILE",[self.ip,port,fileName]))
			elif control == Utils.MESSAGE_HEADER:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,4,(self,self.client)))
				data = Utils.bytesToString(Utils.getPacketOrStop(self.sock,size,(self,self.client)))
				# print(data)
				self.putOtherMessageInChat(data)
			elif control == Utils.LIST_HEADER:
				folderStruc = Utils.listfolder(Utils.UPLOADS_DIR)[0]
				encodedStruc = pickle.dumps(folderStruc)
				size = len(encodedStruc)
				self.sock.send(Utils.LIST_RES_HEADER+Utils.intToBytes(size,4)+encodedStruc)
			elif control == Utils.LIST_RES_HEADER:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,4,(self,self.client)))
				folderStruc = pickle.loads(Utils.getPacketOrStop(self.sock,size,(self,self.client)))
				strippedStruc = self.fillTreeWithFolder(self.browseTree,"",folderStruc,"")
				self.client.setFolderStruc(strippedStruc)
				# self.client.setFolderStruc(folderStruc)
			elif control==Utils.BEAT_HEADER:
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
	connections=[] #(socket,serverthread,clientthread)

	def __init__(self,peerIP,peerPort,listeningPort,uploadsManager,downloadsManager):
		threading.Thread.__init__(self)
		self.peerIP=peerIP
		self.peerPort=peerPort
		self.listeningPort=listeningPort
		self.uploadsManager=uploadsManager
		self.downloadsManager=downloadsManager

	def setChatLog(self,chatLog):
		self.chatLog=chatLog

	def setBrowseTree(self,browseTree):
		self.browseTree=browseTree

	def run(self):
		try:#start off by trying to connect to other peer
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((self.peerIP, self.peerPort))
			self.connectToPeer(s,self.peerIP)
		except:
			pass
		s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s1.bind(('',self.listeningPort))
		s1.listen(1)# number of backloged connections
		while 1:
			s2, addr = s1.accept()
			print('Connection address: '+str(addr))
			self.connectToPeer(s2,addr[0])

	def connectToPeer(self,sock,addressIP):
		client = ClientThread(sock,self.downloadsManager.mailBox)
		server = ServerThread(sock,self.chatLog,self.uploadsManager.mailBox,client,self.browseTree,addressIP)
		client.start()
		server.start()
		print("connected")
		self.connections.append((sock,server,client))

class IndDownloadThread(TransferThread):
	fullFilePath=None#filepath to the client

	def recieveFile(self,sock,size):
		self.fullFilePath = Utils.join(Utils.DOWNLOADS_DIR,self.filePath)
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
			elif remainingsize>=Utils.PACKET_SIZE:
				ret =  Utils.bytesToInt(Utils.getPacketOrStop(sock,1,(self)))
				if ret==0:
					raise CancelException()
				packet = Utils.getPacketOrStop(sock,Utils.PACKET_SIZE,(self))
				remainingsize = remainingsize-Utils.PACKET_SIZE
				if count%10==0:
					percent = format(float(size-remainingsize)/float(size)*100,'.2f')
					self.tree.set(self.treeItem,"progress",str(percent)+"%")#make this happen not as often
				count+=1
			else:
				ret = Utils.bytesToInt(Utils.getPacketOrStop(sock,1,(self)))
				if ret==0:
					raise CancelException()
				packet = Utils.getPacketOrStop(sock,remainingsize,(self))
				remainingsize=0
			f.write(packet)
		f.close()

	def run(self):
		conn = None
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.bind((self.sock.getsockname()[0],0))
			s.listen(1)
			message = Utils.FILE_REQUEST+Utils.intToBytes(len(self.filePath),2)+Utils.stringToBytes(self.filePath)+Utils.intToBytes(s.getsockname()[1],2)#need to also send ip address
			self.sock.send(message)
			conn,addr = s.accept()
			succ = True
			ret = Utils.bytesToInt(Utils.getPacketOrStop(conn,1,(self)))
			if ret==0:
				raise CancelException()
			rec = Utils.getPacketOrStop(conn,9,(self))
			control = rec[:4]
			if control==Utils.SEND_FILE_HEADER:
				size = Utils.bytesToInt(rec[5:])
				self.recieveFile(conn,size)
			elif control == Utils.FILE_NOT_EXIST_ERR:
				print("The Requested File Isn't Being Uploaded By The Peer")
				succ = False
			else:
				print("There Was An Error With The Specified File")
				succ = False
			conn.close()
			if succ:
				self.tree.set(self.treeItem,"progress","Done")
				self.tree.move(self.treeItem,'',0)
			else:
				self.tree.set(self.treeItem,"progress","failed")
			self.managerMailbox.put(("THREAD",(self,self.filePath,succ,self.treeItem)))
		except CancelException:
			self.tree.set(self.treeItem,"progress","cancelled")
			self.setCancelled(True)
			self.cancelDownload(conn)
		except SystemExit:#stopped by another thread
			self.cancelDownload(conn)			
		except:
			print("caught")
			self.tree.set(self.treeItem,"progress","failed")
			print(self.filePath)
			self.managerMailbox.put(("THREAD",(self,self.filePath,False,self.treeItem)))

	def cancelDownload(self,conn):
		if conn!=None:
			conn.close()
		if self.fle!=None:
			self.fle.close()
			os.remove(self.fullFilePath)#check if it exists?
		self.managerMailbox.put(("THREAD",(self,self.filePath,self.isCancelled,self.treeItem)))

class DownloadManagerThread(StoppableThread):#if thread downloads thread crashs make it auto retry
	downloadList=[]#(sock,filename,retries,treeItem)
	folderStruc = None
	downloadTree = None
	downloadThreads=[] # (thread,filename,retryamount) so that if a failed file. it can retry download

	def __init__(self,maxThreads):
		threading.Thread.__init__(self)
		self.mailBox=queue.Queue()
		self.maxThreads=maxThreads

	def setTree(self,downloadTree):
		self.downloadTree=downloadTree

	def appendFiles(self,downloadInfo):#[sock,file,retries]
		self.downloadTree.insert("",END,text=downloadInfo[1][0],values=(downloadInfo[0].getsockname(),downloadInfo[1][1],"Waiting"))
		children = self.downloadTree.get_children('')
		downloadInfo.append(children[len(children)-1])
		self.downloadList.append(tuple(downloadInfo))#abstract this up
		for i in range(len(self.downloadThreads),self.maxThreads):
			self.downloadNext()

	def downloadNext(self):
		if len(self.downloadThreads)<self.maxThreads and len(self.downloadList)>0:
			nextDownloadInfo = self.downloadList.pop(0)
			sock = nextDownloadInfo[0]
			nextFile=nextDownloadInfo[1][0]
			retries=nextDownloadInfo[2]
			treeItem = nextDownloadInfo[3]
			print("going to download "+nextFile)
			t = IndDownloadThread(sock,nextFile,self.mailBox,self.downloadTree,treeItem)
			self.downloadThreads.append((t,nextFile,retries))
			t.start()

	def removeThread(self,itemToRemove):
		try:#in case the thread is no longer in the downloadThreads list
			self.downloadThreads.remove(itemToRemove)
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
				for i in range(0,len(self.downloadThreads)):
					if data[0]==self.downloadThreads[i][0]:
						listItem=self.downloadThreads[i]
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
			for i in range(0,len(self.downloadThreads)):#remove from current downloads
				threadInfo = self.downloadThreads[i]
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
			filePath = Utils.join(Utils.DOWNLOADS_DIR,item["text"]) 
			if os.path.isfile(filePath):
				os.remove(filePath)
			self.downloadTree.set(itemName,"progress","Canceled")

class IndUploadThread(TransferThread):

	def sendFileInfo(self,filename):
		message=""
		size=None
		numofpacks=None
		try:
			size = os.path.getsize(filename)
			numofpacks = math.ceil(size/Utils.PACKET_SIZE)
			message = Utils.SEND_FILE_HEADER+Utils.intToBytes(size,5)

		except:
			print("FILE DOESN'T EXIST")
			self.tree.set(self.treeItem,"progress","DNE")
			message=Utils.padMessage(Utils.FILE_NOT_EXIST_ERR,9)
		self.sock.send(Utils.intToBytes(1,1)+message)
		return size,numofpacks

	def run(self):# tell server user that you are sending and it is sent
		try:
			fullfilename = Utils.join(Utils.UPLOADS_DIR,self.filePath)
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
					data = f.read(Utils.PACKET_SIZE)
					percent = format(float(i)/float(numofpacks)*100,'.2f')
					self.tree.set(self.treeItem,"progress",str(percent)+"%")#make this happen not as often
					self.sock.send(Utils.intToBytes(1,1)+data)
			t1 = time.time()
			Utils.printSpeed(t1-t0,size)
			f.close()
			self.tree.set(self.treeItem,"progress","Done")
			self.managerMailbox.put(("THREAD",(self,self.filePath)))
			self.sock.close()
		except SystemExit:
			self.sock.send(Utils.intToBytes(0,1))
			if self.sock!=None:
				self.sock.shutdown(socket.SHUT_RDWR)
				self.sock.close()
			if self.fle!=None:
				self.fle.close()
			self.managerMailbox.put(("THREAD",(self,self.filePath)))
		except:
			# print(sys.exc_info()[0])
			self.tree.set(self.treeItem,"progress","Failed")
			self.managerMailbox.put(("THREAD",(self,self.filePath)))

class UploadManagerThread(StoppableThread):
	uploadList=[]#(ip,port,filename,treeItem)
	uploadThreads=[] # (thread,filename)
	def __init__(self,maxThreads):
		threading.Thread.__init__(self)
		self.mailBox=queue.Queue()
		self.maxThreads=maxThreads

	def setTree(self,uploadTree):
		self.uploadTree=uploadTree

	def appendFile(self,uploadInfo):# [sockname,port,filename]
		size = 0
		try:
			size = os.path.getsize(Utils.join(Utils.UPLOADS_DIR,uploadInfo[2]))
		except:
			pass
		self.uploadTree.insert("",END,text=uploadInfo[2],values=(str(uploadInfo[0])+" "+str(uploadInfo[1]),size,"Waiting"))
		children = self.uploadTree.get_children('')
		uploadInfo.append(children[len(children)-1])
		self.uploadList.append(tuple(uploadInfo))#abstract this up

		for i in range(len(self.uploadThreads),self.maxThreads):
			self.uploadNext()

	def uploadNext(self):
		if len(self.uploadThreads)<self.maxThreads and len(self.uploadList)>0:      
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
			self.uploadThreads.append((t,nextFile))
			t.start()

	def removeThread(self,itemToRemove):
		self.uploadThreads.remove(itemToRemove)
		self.uploadNext()
	
	def run(self):
		while(1):
			data = self.mailBox.get()
			messageType = data[0]
			data = data[1]
			if messageType == "THREAD":
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
			for i in range(0,len(self.uploadThreads)):#remove from current uploads
				threadInfo = self.uploadThreads[i]
				thread = threadInfo[0]
				if thread.treeItem==itemName:
					thread.stop()
					self.uploadTree.set(itemName,"progress","Canceled")
					break
		else:
			self.uploadList.pop(itemToRemove)