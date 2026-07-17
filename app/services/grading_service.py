from decimal import Decimal,InvalidOperation
import re
class GradingService:
    def equivalent(self,a:str,b:str)->bool:
        def num(x):
            try:
                x=x.strip().replace(',','')
                if x.count('/')==1:
                    n,d=x.split('/'); return Decimal(n)/Decimal(d)
                return Decimal(x)
            except (InvalidOperation,ValueError,ZeroDivisionError): return None
        x,y=num(a),num(b)
        if x is not None and y is not None: return abs(x-y)<=Decimal('0.000001')
        norm=lambda s:re.sub(r'\s+','',s.lower())
        return norm(a)==norm(b)
