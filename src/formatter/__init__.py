

class Formatter(object):
    
    media_type = None # the media type of the format.
    
    def __init__(self, uri, lang, output):
        """
        Formatter for the given URI, writing
        to the callable output(uni_str). Output is Unicode; callee
        is responsible for encoding correctly.
        """
        self.uri = uri
        self.lang = lang
        self.output = output
        
    def feed(self, red, sample):
        """
        Feed a body sample to processor(s).
        """
        raise NotImplementedError
        
    def start_output(self):
        """
        Send preliminary output.
        """
        raise NotImplementedError

    def status(self, status):
        """
        Output a status message.
        """
        raise NotImplementedError        
        
    def finish_output(self, red):
        """
        Finalise output.
        """
        raise NotImplementedError
