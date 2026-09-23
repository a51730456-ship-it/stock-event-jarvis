import numpy as np
import pandas as pd
import pytest
from research.audit_jarvis8_forward import account_path


def test_cash_and_fees_and_entry_timing():
    # Signal close is 50; actual buy next open is 100, so there is no doubled return.
    op=pd.DataFrame({'A':[50,100,110]})
    cl=pd.DataFrame({'A':[50,105,110]})
    nav=account_path(op,cl,['A','A'],0,2,0.,.1)
    assert nav == pytest.approx([1.005,1.01])
    paid=account_path(op,cl,['A'],0,2,1.,.1)
    assert paid[-1] == pytest.approx(.9+.1*1.1/1.005*.995)


def test_missing_held_price_does_not_become_cash():
    op=pd.DataFrame({'A':[50,100,110]})
    cl=pd.DataFrame({'A':[50,np.nan,110]})
    with pytest.raises(ValueError,match='Missing'):
        account_path(op,cl,['A'],0,2)
    assert account_path(op,cl,[],0,2).tolist()==[1.,1.]


def test_no_borrowing_or_overallocation():
    f=pd.DataFrame({'A':[100,100],'B':[100,100]})
    with pytest.raises(ValueError,match='cash'):
        account_path(f,f,['A','B'],0,1,weight=.6)
