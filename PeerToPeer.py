#!python3
import os,socket,queue
import Utils,CustomThreads,test
from tkinter import *
from tkinter import ttk

def mainWindow(master):
	def SendMessageAction():
		message = EntryBox.get("0.0",END).strip()+"\n"
		if message!="\n" and index[0] != None: #empty message
			listeningThread.connections[index[0]][2].mailBox.put(("MESSAGE",message))
			putMyMessageInChat(message)
			chatLog.yview(END)
		EntryBox.delete("0.0",END)

	def putMyMessageInChat(message):
		if index[0] != None:
			listeningThread.addMessage(index[0],("You: ",message))

	def onSelect(event):
		indexList = listBox.curselection()
		if(len(indexList) > 0):
			if index[0]!=None:
				listBox.itemconfig(index[0],bg='Orange')#make this white
			index[0] = int(indexList[0])
			listBox.itemconfig(index[0],bg='red')#make this blue (same color as selecting)
			listeningThread.fillBrowseTab(index[0])
			messages = listeningThread.connections[index[0]][3]
			chatLog.config(state=NORMAL)
			chatLog.delete('1.0',END)
			for i in range(0,len(messages)):
				addMessage(messages[i])
			chatLog.config(state=DISABLED)
			chatLog.yview(END)

	def addMessage(message):
		color = None
		if message[0]=="You: ":
			color = "#FF8000"
		else:
			color = "#04B404"
		Utils.addMessageToLog(chatLog,color,message)

	def PressAction(event):
		EntryBox.config(state=NORMAL)
		SendMessageAction()

	# def DisableEntry(event):
	#   EntryBox.config(state=DISABLED)

	def download():
		selections = browseTree.selection()
		if index[0] != None:
			listeningThread.connections[index[0]][2].mailBox.put(("FILES",selections))

	tabs = ttk.Notebook(master)
	index = [None]
	# arealabel = Label(master,text="Connections:",font=("Times",14,"bold"))
	# arealabel.pack(anchor=NW)
	scrollbary = Scrollbar(master)
	listBox = Listbox(master,yscrollcommand=scrollbary.set)
	listBox.pack(padx=(0,5),side=LEFT,fill=BOTH)
	scrollbary.pack(side=LEFT,fill=Y)
	listBox.bind('<<ListboxSelect>>', onSelect)

	messageTab=Frame(master)
	browseTab=Frame(master)
	messF1=Frame(messageTab)
	messF2=Frame(messageTab)
	browseF1 = Frame(browseTab)
	browseF2 = Frame(browseTab)
	tabs.add(messageTab,text="Messaging",compound=TOP)
	tabs.add(browseTab,text="Browse",compound=TOP)
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

	browseF1.pack(fill=BOTH, expand=True)
	browseF2.pack()

	chatLog = Text(messF1, bd=0, bg="white", height="8", width="50", font="Arial")
	chatLog.config(state=DISABLED)

	scrollbar = Scrollbar(messF1, command=chatLog.yview)#, cursor="heart")
	chatLog['yscrollcommand'] = scrollbar.set

	SendButton = Button(messF2, font=30, text="Send", width="12", height=5, bd=0, bg="#FFBF00", activebackground="#FACC2E",command=SendMessageAction)

	EntryBox = Text(messF2, bd=0, bg="white",width="29", height="5", font="Arial")
	# EntryBox.bind("<Return>", DisableEntry)
	EntryBox.bind("<KeyRelease-Return>", PressAction)

	scrollbar.pack(side=RIGHT,fill=Y,pady=(5,5))
	chatLog.pack(pady=(5,5),fill=BOTH, expand=True)
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

	browseF1.pack(fill=BOTH, expand=True)
	browseF2.pack()

	return chatLog,browseTree,listBox,onSelect

def transferWindow(root,maxUploadThreads,maxdownloadThreads):
	def CancelDownload():
		selections = downloadTree.selection()
		downloadsManager.mailBox.put(("CANCEL",selections))

	def CancelUpload():
		selections = uploadTree.selection()
		print(selections)
		uploadsManager.mailBox.put(("CANCEL",selections))
	
	master = Toplevel(root)
	tabs = ttk.Notebook(master)

	downloadsTab=Frame(master)
	uploadsTab=Frame(master)
	downloadF1 = Frame(downloadsTab)
	downloadF2 = Frame(downloadsTab)
	uploadF1 = Frame(uploadsTab)
	uploadF2 = Frame(uploadsTab)
	tabs.add(downloadsTab,text="Downloads",compound=TOP)
	tabs.add(uploadsTab,text="Uploads",compound=TOP)
	tabs.pack(fill=BOTH, expand=True)

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

	downloadCancelB = Button(downloadF2,text="cancel",command=CancelDownload)
	downloadCancelB.pack()

	downloadF1.pack(fill=BOTH, expand=True)
	downloadF2.pack()

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

	uploadF1.pack(fill=BOTH, expand=True)
	uploadF2.pack()
	
	uploadsManager = CustomThreads.UploadManagerThread(maxUploadThreads,uploadTree)
	downloadsManager = CustomThreads.DownloadManagerThread(maxdownloadThreads,downloadTree)

	return uploadsManager,downloadsManager

if (__name__ == "__main__"):
	username,listeningPort,peerPort,maxUploadThreads,maxdownloadThreads,secretKey = Utils.getSettings()
	possConnectionList = test.getConnections()
	print(possConnectionList)
	master = Tk()
	chatLog,browseTree,listBox,onSelectMethod = mainWindow(master)
	uploadsManager,downloadsManager = transferWindow(master,maxUploadThreads,maxdownloadThreads)
	listeningThread = CustomThreads.ListeningThread(possConnectionList,peerPort,listeningPort,uploadsManager,downloadsManager,chatLog,browseTree,listBox,onSelectMethod,username,secretKey)

	uploadsManager.start()
	downloadsManager.start()
	listeningThread.start()

	mainloop()

	#replace some of the lists with class objects to increase readability
	#rename alot of stuff in connections file
	#abstract settings vs connections file?

	#add upload and download dir to settigns
	#put name instead of "YOU: "

	#make all threads close if gui closes
	#slow down heartbeat rate (it seems to send alot faster than 15 seconds)
	#allow shift down
	#if a locked file is in the uploads dir it shouldn't try to acess it
	#remove connections
	#if uploader closes gui try to make it fail better :)
	#max the size of saved messages
	#make getpacket not be an active wait
	#what if i write bytes into the settings file?
	#fix gui lag while downloading
	#make sure space on hard drive before starting a download
	#encryption :)
	#set proper update rates for upload and downloads
	#allow dynamically add and delete files to their upload folders
	#if a download is 50% and request it again it starts at 50% not 0%
	#move canceled downloads below completed and above current
	#what if download same filename from different peers
	#make it so if a peer is full on uploads a requesting downloader doesn't wait all day
	#display max upload/downloads allow it to be changed but error check that its <= 100 and > 0
	#allow user to clear finished uploaded or downloaded files
	#maintain ip address
	#make a help or about menu
	#errors
	#add max up/download to screen, add clear, add cancel/cancell all, add clear completed checkbox
	#spawn new processes for fuller parallelism (downloader and uploader)