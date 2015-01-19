class LuaError(Exception):
	def __str__(self):
		return repr("illegal lua string")

class LuaLengthError(Exception):
	def __str__(self):
		return repr("out of range")

class PyError(Exception):
	def __str__(self):
		return repr("illegal python type")

class FpError(Exception):
	def __str__(self):
		return repr("python file IO exception")

class PyLuaTblParser(object):
	def __init__(self):
		self.data = {}
		self.strlen = None

	def load(self, s):
		self.strlen = len(s)
		self.data, begin = self.parseTable(s, 0)
		begin = self.escape(s, begin)
		if begin < self.strlen: raise LuaError()

	def equals(self, s, begin, end, t):
		strlen = self.strlen
		if end > strlen: return False
		return s[begin:end] == t

	def escapeWhitespace(self, s, begin):
		strlen = self.strlen
		blankSpace = " \t\r\n"
		prePos = begin
		while (begin < strlen) and blankSpace.find(s[begin]) > -1:
			begin += 1
		return begin

	def escapeComment(self, s, begin):
		strlen = self.strlen
		if self.equals(s, begin, begin + 3, "--["):
			end = begin + 3
			while self.equals(s, end, end + 1, "="):	# lua block comment ?
				end += 1
			if self.equals(s, end, end + 1, "["):		# lua blocak comment
				right = "]" + s[begin+3:end] + "]"		# ]=== ...]
				length = end-begin-1
				end += 1
				while (end+length <= strlen) and \
				(s[end:end+length] != right):
					end += 1
				if end + length > strlen:
					raise LuaError()
				else:
					return end + length
			else:
				while (end < strlen) and (s[end] != '\n'):		# lua line comment
					end += 1
				return end + 1
		else:
			end = begin + 2
			while (end < strlen) and (s[end] != '\n'):			# line escapeComment
				end += 1
			return end + 1

	def check(self, begin):
		if begin >= self.strlen: raise LuaError()
		return True

	# escape whitespace and lua comment
	def escape(self, s, begin):
		while begin < self.strlen:
			begin = self.escapeWhitespace(s, begin)
			if self.equals(s, begin, begin+2, "--"):
				begin = self.escapeComment(s, begin)
			else:
				break
		return begin

	def store(self, di, maxn, isList):
		if isList:
			tempList = []
			for i in range(1, maxn):
				tempList.append(di[i])
			return tempList
		else:
			tempDict = {}
			for k, v in di.iteritems():
				if v != None:
					tempDict[k] = v
			return tempDict
 
	def isRecordType(self, char):
		return (char == '_' or char.isdigit() \
		or char.isalpha())

	def isNumber(self, number):
		return (isinstance(number, int) or \
		isinstance(number, long) or \
		isinstance(number, float))

	def isString(self, string):
		return (isinstance(string, str) or \
		isinstance(string, unicode))

	def checkConstant(self, key):
		if key == "nil": return True, None
		if key == "true": return True, True
		if key == "false": return True, False
		
		return False, None

	def dealConstant(self, s, begin, key, maxn, tempDict, is_List):
		isKey, value = self.checkConstant(key)
		if isKey:
			tempDict[maxn] = value
			maxn += 1
		else:
			is_List = False
			begin = self.escape(s, begin)
			self.check(begin)
									
			if s[begin] == '=':					# is a (key, value) pair
				begin += 1
				value, begin = self.parseValue(s, begin)
				tempDict[key] = value
		return begin, maxn, is_List


	# need to handle ,; more
	def parseTable(self, s, begin):
		tempDict = {}
		maxn = 1
		isList = True
		invalidTwoKeyValue = False 					# check if have {[k]=v [k]=v}
		invalidTwoOptor = True 						# check if have {,;} there is no other word between tow , or ;
		empty = True 				

		begin = self.escape(s, begin)				# escape whitespace and lua comment
		self.check(begin)
		if s[begin] != '{': raise LuaError()		# check {
		begin += 1
				
		while True:
			begin = self.escape(s, begin)	# escape whitespace and lua comment
			self.check(begin)
			# parse a table
			if s[begin] == '}':
				if empty: return {}, begin+1
				return self.store(tempDict, maxn, isList), begin+1
			# is delimiter
			elif s[begin] == ',' or s[begin] == ';':
				if invalidTwoOptor: raise LuaError()
				else:
					invalidTwoOptor = True
					invalidTwoKeyValue = False
					begin += 1
			else:
				if invalidTwoKeyValue: raise LuaError()
				invalidTwoKeyValue = True
				invalidTwoOptor = False
				# is a new table
				if s[begin] == '{':
					value, begin = self.parseTable(s, begin)
					tempDict[maxn] = value
					maxn += 1
				# is lua string
				elif self.equals(s, begin, begin+2, "[["):
					value, begin = self.parseString(s, begin)
					tempDict[maxn] = value
					maxn += 1
				# is a ([key] = value) pair
				elif s[begin] == '[':
					# parse key
					isList = False
					begin, key, value = self.parsePair(s, begin, tempDict)
					if self.isNumber(key) and (key in tempDict): continue
					tempDict[key] = value

				# is lua shortcut  recordType {a = 3}
				elif s[begin] == '_' or s[begin].isalpha():
					key, begin = self.parseRecordValue(s, begin)
					begin, maxn, isList = self.dealConstant(s, begin, key, maxn, tempDict, isList)

				# is lua string or number
				elif s[begin] == '"' or s[begin] == "'" or \
					 ("-0123456789.".find(s[begin]) > -1):
					value, begin = self.parseString(s, begin)
					tempDict[maxn] = value
					maxn += 1
				# illegal character
				else:
					raise LuaError()
			empty = False

	def parsePair(self, s, begin, tempDict):
		begin += 1
		key, begin = self.parseValue(s, begin)
		begin = self.escape(s, begin)
		self.check(begin)
		if s[begin] != ']': raise LuaError()
		#parse value
		begin += 1
		begin = self.escape(s, begin)
		self.check(begin)
		if s[begin] != '=': raise LuaError()
		begin += 1
		value, begin = self.parseValue(s, begin)
		return begin, key, value

	def parseNumber(self, s, begin):
		sign = 1
		end = begin
		if s[end] == "-":
			sign = -1
			end += 1
		# base 16
		if self.equals(s, end, end+2, "0x"):
			end += 2
			begin = end
			dot = None
			number = False
			while (end < self.strlen):		# end < len(s) ????
				if s[end] == '.':
					if dot: raise LuaError()
					dot = end
				elif ("0123456789abcedf".find(s[end].lower()) > -1):
					end += 1
					number = True
				else:
					break
			if not number: raise LuaError()
			if not dot: dot = end
			# number before dot
			a = 0
			for i in range(begin, dot):
				a = a * 16 + int(s[i], 16)
			# number after dot
			b = 0
			for i in reversed(range(dot+1, end)):
				b = (b + int(s[i], 16)) / 16.0
			number = sign * (a + b)
			self.check(end)
			# ends with p123...
			if s[end].lower() == "p":
				end += 1
				begin = end
				self.check(end)
				while (end < self.strlen) and \
				("-0123456789".find(s[end]) > -1):
					end += 1
				try:
					p = int(s[begin:end])
					number *= math.pow(2, p)
					return number, end
				except:
					raise LuaError()
			else:
				return number, end
		# base 10
		else:
			while (end < self.strlen) and \
			("+-0123456789.eE".find(s[end].lower()) > -1):
				end += 1
			try:
				number = eval(s[begin:end])
				return number, end
			except:
				raise LuaError()

	def dealString(self, s, begin, endChar):
		escapeList = {
			'\\\"': '"',
			"\\\'": "'",
			"\\b": "\b",
			"\\f": "\f",
			"\\r": "\r",
			"\\n": "\n",
			"\\t": "\t",
			"\\\\":"\\",
			"\\/": "/",
			"\\a": "\a",
			"\\v": "\v",
			"\\u": "\u"
		}
		if self.equals(s, begin, begin+2, "[["):
			begin += 2
		else:
			begin += 1
		stringList = []
		if endChar == "]]":
			while True:
				self.check(begin)
				if self.equals(s, begin, begin+2, endChar):
					return "".join(stringList), begin + 2
				elif s[begin] == "\\":
					found = False
					for k in escapeList:
						if self.equals(s, begin, begin+2, k):
							stringList.append(escapeList[s[begin+1]])
							begin += 2
							found = True
							break
					if not found: raise LuaError()
				else:
					stringList.append(s[begin])
					begin += 1
		else:
			while True:
				self.check(begin)			
				if s[begin] == endChar:						#allow " in string? ("\"")
					return "".join(stringList), begin + 1
				elif s[begin] == "\\":
					found = False
					for k in escapeList:
						if self.equals(s, begin, begin+2, k):
							stringList.append(escapeList[k])
							begin += 2
							found = True
							break
					if not found: raise LuaError()
				else:
					stringList.append(s[begin])
					begin += 1

	def parseString(self, s, begin):
		li = []
		isStr = False
		while True:
			if ("-0123456789.eE".find(s[begin]) > -1):
				number, begin = self.parseNumber(s, begin)
				li.append(str(number))
			else:
				isStr = True
				substr = None
				if s[begin] == '"':
					substr, begin = self.dealString(s, begin, '"')
				elif s[begin] == "'":
					substr, begin = self.dealString(s, begin, "'")
				elif self.equals(s, begin, begin+2, "[["):
					substr, begin = self.dealString(s, begin, "]]")
				else:
					raise LuaError()
				li.append(substr)
			begin = self.escape(s, begin)
			self.check(begin)
			# may be need concat
			if self.equals(s, begin, begin+2, ".."):
				begin += 2
				self.check(begin)
				# more dot ?
				if s[begin] == ".": raise LuaError()
				isStr = True
				self.escape(begin)
				self.check(begin)
			else:
				break
		if isStr: return "".join(li), begin
		else: return eval(li[-1]), begin

	def parseConstant(self, s, begin):
		end = begin
		while (end < self.strlen) and s[end].isalpha():
			end += 1
		# is nil
		if s[begin:end] == 'nil':
			return None, end
		# is true
		elif s[begin:end] == 'true':
			return True, end
		# is false
		elif s[begin:end] == 'false':
			return False, end
		# error
		else:
			raise LuaError()

	def parseRecordValue(self, s, begin):
		end = begin
		while (end < self.strlen) and self.isRecordType(s[end]):
			end += 1
		return s[begin:end], end

	def parseValue(self, s, begin):
		# escape whitespace and lua comment
		begin = self.escape(s, begin)
		self.check(begin)
		if s[begin] == '{':
			return self.parseTable(s, begin)
		elif s[begin] == 'n' or s[begin] == 't' \
			 or s[begin] == 'f':
			return self.parseConstant(s, begin)
		elif self.equals(s, begin, begin+2, "[[") or \
		s[begin] == "'" or s[begin] == '"' or \
		("-0123456789.eE".find(s[begin]) > -1):
			return self.parseString(s, begin)
		else:
			raise LuaError()

	def dumpNone(self):
		return "nil"

	def dumpBool(self, v):
		if v == True:
			return "true"
		else:
			return "false"

	def dumpNumber(self, v):
		return str(v)

	def dumpString(self, v):
		escapeList = {
			"\a": "\\a",
			"\b": "\\b",
			"\f": "\\f",
			"\n": "\\n",
			"\r": "\\r",
			"\t": "\\t",
			"\v": "\\v",
			"\"": '\\\"',
			"\'": "\\\'",
			"\\": "\\\\"
		}
		"""
		if isinstance(v, unicode):
			v = v.encode("utf-8")
		"""
		tempList = []
		for c in v:
			if c in escapeList:
				tempList.append(escapeList[c])
			else:
				tempList.append(c)
		s = "".join(tempList)
		if s.find('"') > -1:
			return "'" + s + "'"
		else:
			return '"' + s + '"'

	def dumpList(self, v):
		tempList = []
		for e in v:
			tempList.append(self.dumpValue(e))
		return "{" + ",".join(tempList) + "}"

	def dumpTable(self, v):
		li = []
		for key, val in v.iteritems():
			if isinstance(key, tuple) or isinstance(key, complex):
				raise PyError()
			if isinstance(val, tuple) or isinstance(val, complex):
				raise PyError()
			li.append("[" + self.dumpValue(key) + "]=" + self.dumpValue(val))
		return "{" + ",".join(li) + "}"

	def dumpValue(self, v):
		# is None
		if v == None:
			return self.dumpNone()
		# is bool
		elif isinstance(v, bool):
			return self.dumpBool(v)
		# is str
		elif self.isString(v):
			return self.dumpString(v)
		# is list
		elif isinstance(v, list):
			return self.dumpList(v)
		# is dict
		elif isinstance(v, dict):
			return self.dumpTable(v)
		elif self.isNumber(v):
			return self.dumpNumber(v)
		else:
			raise PyError()

	def dump(self):
		return self.dumpValue(self.data)
 
	def loadLuaTable(self, f):
		input_list = []
		fp = None
		try:
			fp = open(f, "r")
		except:
			raise FpError()
		try:
			input_list = fp.readlines()
		except:
			raise FpError()
		finally:
			fp.close()
		s = "".join(input_list)
		self.load(s)

	def dumpLuaTable(self, f):
		fp = None
		try:
			fp = open(f, "w")
		except:
			raise FpError()
		lua_tbl = self.dump()
		try:
			fp.write(lua_tbl)
		except:
			raise FpError()
		finally:
			fp.close()

	def loadValue(self, v):
		if isinstance(v, list):
			li = []
			for e in v:
				li.append(self.loadValue(e))
			return li
		elif isinstance(v, dict):
			dt = {}
			for k, e in v.iteritems():
				dt[k] = self.loadValue(e)
			return dt
		else:
			return v

	def loadDict(self, d):
		dt = {}
		if isinstance(d, list):
			for k, v in enumerate(d):
				dt[k] = self.loadValue(v)
		elif isinstance(d, dict):
			for k, v in d.iteritems():
				if self.isString(k) or self.isNumber(k):
					dt[k] = self.loadValue(v)
		self.data = dt

	def dumpDict(self):
		dt = {}
		if isinstance(self.data, list):
			for k, v in enumerate(self.data):
				dt[k] = self.loadValue(v)
		elif isinstance(self.data, dict):
			for k, v in self.data.iteritems():
				dt[k] = self.loadValue(v)
		return dt

if __name__ == "__main__":
	a1 = PyLuaTblParser()
	a2 = PyLuaTblParser()
	a3 = PyLuaTblParser()
	test_str = '{array = {65,23,5,"\\\"ab"},dict = {mixed = {43,54.33,false,9,string = "value",true, NullEmpt=nil, [6] = 1},array = {3,6,4,},string = "value","",},"stringTest"}'
	test_str2 = '{array = {65,23,5,3,"",},}'
	test_str3 = '{["/\\\\\\\"\\b\\f\\n\\r\\t`1~!@#$%^&*()_+-=[]{}|;:\\\',./<>?"] = -12E+10}'
	test_str4 = '{["\\\\\\\""] = "c"}'
	a1.load(test_str)
	d1 = a1.dumpDict()
	print d1	
	a2.loadDict(d1)
	print a1.dump()
	a2.dumpLuaTable("error.txt")
 	a3.loadLuaTable("error.txt")
 	d3 = a3.dumpDict()

 	'''for k, v in enumerate(d1):
 		print "k is %s, v is %s" % (k, v)'''

