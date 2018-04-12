class TableAccumulator(object):
    def __init__(self, channels, memsize=1000000):
        object.__init__(self)
        self.channels=channels
        self.data=[[] for _ in channels]
        self.memsize=memsize

    def add_data(self, data):
        if isinstance(data,dict):
            table_data=[]
            for ch in self.channels:
                if ch not in data:
                    raise KeyError("data doesn't contain channel {}".format(ch))
                table_data.append(data[ch])
            data=table_data
        minlen=min([len(incol) for incol in data])
        for col,incol in zip(self.data,data):
            col.extend(incol[:minlen])
            if len(col)>self.memsize:
                del col[:len(col)-self.memsize]
    def reset_data(self, maxlen=0):
        for col in self.data:
            del col[:len(col)-maxlen]
    
    def get_data_table(self, channels=None, maxlen=None):
        channels=channels or self.channels
        data=[]
        for ch in channels:
            col=self.data[self.channels.index(ch)]
            if maxlen is not None:
                col=col[-maxlen:]
            data.append(col)
        return data
    def get_data_dict(self, maxlen=None):
        return dict(zip(self.channels,self.get_data_table(maxlen=maxlen)))
    