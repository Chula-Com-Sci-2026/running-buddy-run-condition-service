import time
from uuid import uuid4
import jwt
import pytest
from fastapi import HTTPException
from common import user,issue,token_key,ISSUER,AUDIENCE

def test_token_validation_rejects_expiry_wrong_audience_and_forgery():
    subject=str(uuid4())
    valid=issue(subject)
    assert user("Bearer "+valid)["sub"]==subject
    now=int(time.time())
    for overrides,key in [({"exp":now-1},token_key()),({"aud":"other"},token_key()),({},"incorrect-signing-key")]:
        claims={"sub":subject,"iss":ISSUER,"aud":AUDIENCE,"iat":now,"exp":now+900,**overrides}
        token=jwt.encode(claims,key,algorithm="HS256")
        with pytest.raises(HTTPException) as failure:
            user("Bearer "+token)
        assert failure.value.status_code==401
