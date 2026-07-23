class Citation:
    def __init__(self, title, author, date, source_type="website"):
        self.title = title
        self.author = author
        self.date = date
        self.source_type = source_type

    # APA Format
    def apa(self):
        return f"{self.author}. ({self.date}). {self.title}. {self.source_type.capitalize()}."

    # MLA Format
    def mla(self):
        return f"{self.author}. \"{self.title}.\" {self.source_type.capitalize()}, {self.date}."

    # Chicago Format
    def chicago(self):
        return f"{self.author}. {self.title}. ({self.date}). {self.source_type.capitalize()}."
