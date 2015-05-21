#!python3
import os,socket,queue
import Utils,CustomThreads
from tkinter import *
from tkinter import ttk

def mainWindow(listeningThread):
	def SendMessageAction():
		message = EntryBox.get("0.0",END).strip()+"\n"
		if message!="\n": #empty message
			listeningThread.connections[0][2].mailBox.put(("MESSAGE",message))#send message to first person you connected to
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
		listeningThread.connections[0][2].mailBox.put(("FILES",selections))#request file from first person you connected to

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
	peerIP,peerPort,listeningPort,maxUploadThreads,maxdownloadThreads = Utils.getSettings()
	
	UPLOADS_MANAGER = CustomThreads.UploadManagerThread(maxUploadThreads)
	DOWNLOADS_MANAGER = CustomThreads.DownloadManagerThread(maxdownloadThreads)
	listeningThread = CustomThreads.ListeningThread(peerIP,peerPort,listeningPort,UPLOADS_MANAGER,DOWNLOADS_MANAGER)

	
	mainWindow(listeningThread)

	#refactor
	#abstract up thread methods
	#replace some of the lists with class objects to increase readability

	#settings for list of ip's
	#put ip address instead of "Other" in chat

	#make all threads close if gui closes
	#make getpacket not be an active wait
	#put hardcoded strings to headers
	#fix gui lag while downloading
	#set proper update rates for upload and downloads
	#allow dynamically add and delete files to their upload folders
	#if a download is 50% and request it again it starts at 50% not 0%
	#move canceled downloads below completed and above current
	#what if download same filename from different peers
	#make it so if a peer is full on uploads a requesting downloader doesn't wait all day
	#display max upload/downloads allow it to be changed but error check that its <= 100 and > 0
	#allow user to clear finished uploaded or downloaded files
	#make distinction between system message,other messages and your own
	#what if gui is closed before all threads are finished?
	#maintain ip address
	#errors
	#add max up/download to screen, add clear, add cancel/cancell all, add clear completed checkbox
	#spawn new processes for fuller parallelism (downloader and uploader)