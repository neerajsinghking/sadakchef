class SOP(db.Model):
    __tablename__ = 'sops'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    discontinued_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<SOP {self.title}>'
        
    def discontinue(self):
        """Mark SOP as discontinued"""
        self.is_active = False
        self.discontinued_at = datetime.utcnow()
        
    def reactivate(self):
        """Reactivate a discontinued SOP"""
        self.is_active = True
        self.discontinued_at = None 