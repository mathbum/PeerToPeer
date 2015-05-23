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

class ManagerThread(StoppableThread):
	def __init__(self,maxThreads,tree):
		super().__init__()
		self.mailBox=queue.Queue()
		self.maxThreads=maxThreads
		self.transferList=[]
		self.transferThreads=[]
		self.tree = tree

	def removeThread(self,itemToRemove):
		try: #in case the thread is no longer in the transferThreads list
			self.transferThreads.remove(itemToRemove)
		except:
			pass
		self.transferNext()
	
	def run(self):
		while(1):
			data = self.mailBox.get()
			messageType = data[0]
			data = data[1]
			self.handleMail(messageType,data)

	def handleMail(self,messageType,data):
		if messageType == "THREAD":
			self.handleThread(data)
		elif messageType=="CANCEL":
			self.handleCancel(data)
		elif messageType=="FILES":
			self.handleFile(data)
		else:
			self.handleOtherMail(messageType,data)

	def handleCancel(self,data):
		for i in range(0,len(data)):
			self.cancelTransfer(data[i])

	def handleOtherMail(self,messageType,data):
		print("Got Unknown Mail",messageType)

	def cancelTransfer(self,itemName):
		handled = False
		item = self.tree.item(itemName)
		progress = item["values"][2]
		if progress == "Done":
			return True

		itemToRemove = None
		for i in range(0,len(self.transferList)):#remove from list waiting to transfer
			if self.transferList[i][3]==itemName:
				self.tree.set(itemName,"progress","Canceled")
				itemToRemove = i
				handled=True
				break

		if not(handled):
			for i in range(0,len(self.transferThreads)):#remove from current transfer
				threadInfo = self.transferThreads[i]
				thread = threadInfo[0]
				if thread.treeItem==itemName:
					thread.setCanceled(True)
					thread.stop()
					self.tree.set(itemName,"progress","Canceled")
					handled=True
					break
		else:
			self.transferList.pop(itemToRemove)
		return handled

class TransferThread(StoppableThread):
	def __init__(self,sock,filePath,mailbox,tree,treeItem):
		super().__init__()
		self.sock = sock
		self.filePath=filePath#filepath to the server and download manager
		self.managerMailbox=mailbox   
		self.tree=tree
		self.treeItem = treeItem
		self.fle=None#actual file object
		self.isCanceled = False

	def setCanceled(self,isCanceled):
		self.isCanceled=isCanceled

class ListeningThread(StoppableThread):
	def __init__(self,peerIP,peerPort,listeningPort,uploadsManager,downloadsManager,chatLog,browseTree,listBox,onSelectMethod):
		super().__init__()
		self.peerIP=peerIP
		self.peerPort=peerPort
		self.listeningPort=listeningPort
		self.uploadsManager=uploadsManager
		self.downloadsManager=downloadsManager
		self.chatLog = chatLog
		self.browseTree = browseTree
		self.listBox = listBox
		self.onSelectMethod=onSelectMethod
		self.selectedIndex=None
		self.connections=[] #(socket,serverthread,clientthread,messagelist)

	def run(self):
		try:#start off by trying to connect to other peer
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((self.peerIP, self.peerPort))
			self.connectToPeer(s,self.peerIP)

			# s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			# s.connect((self.peerIP, 5007))
			# self.connectToPeer(s,self.peerIP)
			# s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			# s.connect((self.peerIP, 5008))
			# self.connectToPeer(s,self.peerIP)
		except:
			pass
		s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# self.listeningPort=5007
		# self.listeningPort=5008
		# self.listeningPort=5009

		s1.bind(('',self.listeningPort))
		s1.listen(1)# number of backloged connections
		while 1:
			s2, addr = s1.accept()
			print('Connection address: '+str(addr))
			self.connectToPeer(s2,addr[0])

	def addOtherMessage(self,server,message):
		index = None#and if none matches? possible?
		for i in range(0,len(self.connections)):
			if(self.connections[i][1]==server):
				index=i
				break
		self.connections[index][3].append(message)
		if self.selectedIndex==index:
			self.putMessageInLog(message,False)
		else:
			self.listBox.itemconfig(index,bg="yellow")
			pass#hilight the listitem
		Utils.playGotMessageSound()

	def addMessage(self,index,message):
	  self.connections[index][3].append(message)
	  if self.selectedIndex==index:
	  	self.putMessageInLog(message,True)

	def putMessageInLog(self,message,fromSelf):
		self.chatLog.config(state=NORMAL)
		color = None
		if fromSelf:
			color = "#FF8000"
		else:
			color = "#04B404"
		Utils.addMessageToLog(self.chatLog,color,message)
		self.chatLog.config(state=DISABLED)
		self.chatLog.yview(END)

	def connectToPeer(self,sock,addressIP):
		client = ClientThread(sock,self.downloadsManager.mailBox)
		server = ServerThread(sock,self.uploadsManager.mailBox,client,self.browseTree,addressIP,self)
		client.start()
		server.start()
		self.connections.append((sock,server,client,[]))
		self.listBox.insert(END,addressIP)
		if self.selectedIndex==None:
			self.selectedIndex=0
			self.listBox.select_set(0)
		self.onSelectMethod(None)

	def fillBrowseTab(self,index):
		self.connections[index][1].fillBrowseTree()
		self.selectedIndex=index

class ServerThread(StoppableThread):
	def __init__(self,sock,managerMailbox,client,browseTree,ip,listeningThread):
		super().__init__()
		self.sock=sock
		self.managerMailbox=managerMailbox
		self.client=client
		self.browseTree=browseTree
		self.ip = ip
		self.listeningThread=listeningThread
		self.peerFolderStruc=None

	def run(self):
		while 1:
			control = Utils.getPacketOrStop(self.sock,4,(self,self.client))
			print(control)
			if control == Utils.FILE_REQUEST:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,2,(self,self.client)))
				fileName = Utils.bytesToString(Utils.getPacketOrStop(self.sock,size,(self,self.client)))
				port = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,2,(self,self.client)))
				print("ip to send to "+self.ip)
				self.managerMailbox.put(("FILES",[self.ip,port,fileName]))
			elif control == Utils.MESSAGE_HEADER:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,4,(self,self.client)))
				data = Utils.bytesToString(Utils.getPacketOrStop(self.sock,size,(self,self.client)))
				self.putOtherMessageInChat(data)
			elif control == Utils.LIST_HEADER:
				folderStruc = Utils.listfolder(Utils.UPLOADS_DIR)[0]
				encodedStruc = pickle.dumps(folderStruc)
				size = len(encodedStruc)
				self.sock.send(Utils.LIST_RES_HEADER+Utils.intToBytes(size,4)+encodedStruc)
			elif control == Utils.LIST_RES_HEADER:
				size = Utils.bytesToInt(Utils.getPacketOrStop(self.sock,4,(self,self.client)))
				self.peerFolderStruc = pickle.loads(Utils.getPacketOrStop(self.sock,size,(self,self.client)))
				strippedStruc = self.stripFolderStruc(self.peerFolderStruc,"")
				self.client.setFolderStruc(strippedStruc)
			elif control==Utils.BEAT_HEADER:
				pass

	def putOtherMessageInChat(self,message):
		self.listeningThread.addOtherMessage(self,(self.ip+": ",message))

	def stripFolderStruc(self,filestruc,path):
		"""Returns folderstruc without folder sizes"""
		folder = []
		for i in range(0,len(filestruc)):
			item = filestruc[i]
			if isinstance(item,list):#if its a folder
				itempath = Utils.join(path,item[0][0])
				prevfold=self.stripFolderStruc(item[1],itempath)
				prevfold.insert(0,itempath)
				folder.append(prevfold)
			else:#if its a file
				fileext = os.path.splitext(item[0])[1]
				folder.append((Utils.join(path,item[0]),item[1]))
		return folder

	def fillBrowseTree(self):
		for i in self.browseTree.get_children():
			self.browseTree.delete(i)
		self.fillTreeWithFolder(self.browseTree,"",self.peerFolderStruc,"")

	def fillTreeWithFolder(self,tree,root,filestruc,path):
		for i in range(0,len(filestruc)):
			item = filestruc[i]
			if isinstance(item,list):#if its a folder
				itempath = Utils.join(path,item[0][0])
				direc = tree.insert(root,END,itempath,text=item[0][0],values=(item[0][1],""))
				self.fillTreeWithFolder(tree,direc,item[1],itempath)
			else:#if its a file
				fileext = os.path.splitext(item[0])[1]
				tree.insert(root,END,Utils.join(path,item[0]),text=item[0],values=(item[1],fileext))

class ClientThread(StoppableThread):#responsible for sending messages to peer
	def __init__(self,sock,managerMailbox):
		super().__init__()
		self.sock=sock
		self.mailBox=queue.Queue()
		self.managerMailbox = managerMailbox
		self.folderStruc=None

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

class UploadManagerThread(ManagerThread):
	# transferList=[]#(ip,port,filename,treeItem)
	# transferThreads=[] # (thread,filename)

	def appendFile(self,uploadInfo):# [ip,port,filename]
		size = 0
		try:
			size = os.path.getsize(Utils.join(Utils.UPLOADS_DIR,uploadInfo[2]))
		except:
			pass
		self.tree.insert("",END,text=uploadInfo[2],values=(str(uploadInfo[0])+" "+str(uploadInfo[1]),size,"Waiting"))
		children = self.tree.get_children('')
		uploadInfo.append(children[len(children)-1])
		self.transferList.append(tuple(uploadInfo))

		for i in range(len(self.transferThreads),self.maxThreads):
			self.transferNext()

	def transferNext(self):
		if len(self.transferThreads)<self.maxThreads and len(self.transferList)>0:      
			nextFileInfo = self.transferList.pop(0)
			ip = nextFileInfo[0]
			port = nextFileInfo[1]
			nextFile=nextFileInfo[2]
			treeItem = nextFileInfo[3]
			print("going to upload "+nextFile)

			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((ip, port))
			print("connected: "+str(ip)+" "+str(port))

			t = IndUploadThread(s,nextFile,self.mailBox,self.tree,treeItem)
			self.transferThreads.append((t,nextFile))
			t.start()

	def handleThread(self,data):
		print("Upload thread returned")
		self.removeThread(data)

	def handleFile(self,data):#if its a new file to upload [ip,port,filename]
		self.appendFile(data)

class DownloadManagerThread(ManagerThread):
	# self.transferList=[]#(sock,filename,retries,treeItem)
	# transferThreads=[] # (thread,filename,retryamount) so that if a failed file. it can retry download

	def appendFiles(self,downloadInfo):#[sock,file,retries]
		self.tree.insert("",END,text=downloadInfo[1][0],values=(downloadInfo[0].getsockname(),downloadInfo[1][1],"Waiting"))
		children = self.tree.get_children('')
		downloadInfo.append(children[len(children)-1])
		self.transferList.append(tuple(downloadInfo))
		for i in range(len(self.transferThreads),self.maxThreads):
			self.transferNext()

	def transferNext(self):
		if len(self.transferThreads)<self.maxThreads and len(self.transferList)>0:
			nextDownloadInfo = self.transferList.pop(0)
			sock = nextDownloadInfo[0]
			nextFile=nextDownloadInfo[1][0]
			retries=nextDownloadInfo[2]
			treeItem = nextDownloadInfo[3]
			print("going to download "+nextFile)
			t = IndDownloadThread(sock,nextFile,self.mailBox,self.tree,treeItem)
			self.transferThreads.append((t,nextFile,retries))
			t.start()

	def handleThread(self,data):#if its a thread done (thread,filepath,succ,treeItem)
		print("download thread returned: "+str(data[2]))
		listItem = None
		for i in range(0,len(self.transferThreads)):
			if data[0]==self.transferThreads[i][0]:
				listItem=self.transferThreads[i]
				break
		print(data)
		if not(data[2]):#unsucessful download
			retries = listItem[2]-1
			if retries>0:
				self.transferList.insert(0,(data[0].sock,(data[1],-1),retries,data[3]))
				self.tree.set(data[3],"progress","waiting")
		self.removeThread(listItem)

	def handleFile(self,data):#if its a new files to download format [sock,file,retrylimit]
		self.appendFiles(data)
	
	def cancelTransfer(self,itemName):
		handled = super().cancelTransfer(itemName)

		if not(handled):#remove from completed download that was canceled before it completed
			item = self.tree.item(itemName)
			filePath = Utils.join(Utils.DOWNLOADS_DIR,item["text"]) 
			try:
				if os.path.isfile(filePath):
					os.remove(filePath)
			except:
				pass
			self.tree.set(itemName,"progress","Canceled")

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

	def run(self):
		try:
			fullfilename = Utils.join(Utils.UPLOADS_DIR,self.filePath)
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

class IndDownloadThread(TransferThread):
	def __init__(self,sock,filePath,mailbox,tree,treeItem):
		super().__init__(sock,filePath,mailbox,tree,treeItem)
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
				self.tree.set(self.treeItem,"progress","Failed")
			self.managerMailbox.put(("THREAD",(self,self.filePath,succ,self.treeItem)))
		except CancelException:
			self.tree.set(self.treeItem,"progress","Canceled")
			self.setCanceled(True)
			self.cancelDownload(conn)
		except SystemExit:#stopped by another thread
			self.cancelDownload(conn)     
		except:
			print("caught")
			self.tree.set(self.treeItem,"progress","Failed")
			print(self.filePath)
			self.managerMailbox.put(("THREAD",(self,self.filePath,False,self.treeItem)))

	def cancelDownload(self,conn):
		if conn!=None:
			conn.close()
		if self.fle!=None:
			self.fle.close()
			try:
				os.remove(self.fullFilePath)#check if it exists?
			except:
				pass
		self.managerMailbox.put(("THREAD",(self,self.filePath,self.isCanceled,self.treeItem)))