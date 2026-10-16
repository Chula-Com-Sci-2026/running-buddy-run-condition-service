from datetime import datetime,timedelta,timezone
import httpx
import pytest
from conftest import auth
import app as module

def test_real_redis_cache_hit_expiry_and_stale_fallback(client,subject,monkeypatch):
    module.cache.flushdb()  # Test runner supplies a dedicated Redis database.
    at=(datetime.now(timezone.utc)+timedelta(days=1)).replace(minute=0,second=0,microsecond=0)
    stamp=at.strftime('%Y-%m-%dT%H:00')
    calls=[]
    def get(self,url,**kwargs):
        calls.append(url)
        hourly={'time':[stamp],'pm2_5':[15]} if 'air-quality' in url else {'time':[stamp],'temperature_2m':[29],'relative_humidity_2m':[60],'precipitation_probability':[10]}
        return httpx.Response(200,json={'hourly':hourly},request=httpx.Request('GET',url))
    monkeypatch.setattr(httpx.Client,'get',get)
    params={'latitude':13.73,'longitude':100.541,'at':at.isoformat()}
    one=module.conditions(**{**params,'at':at},claims={})
    assert not one['cacheHit'] and len(calls)==2
    assert 0<module.cache.ttl(one['cacheKey'])<=900
    two=module.conditions(**{**params,'at':at},claims={})
    assert two['cacheHit'] and len(calls)==2
    module.cache.delete(one['cacheKey'])
    def down(*args,**kwargs):raise httpx.ConnectError('offline')
    monkeypatch.setattr(httpx.Client,'get',down)
    assert module.conditions(**{**params,'at':at},claims={})['stale']
    module.cache.delete('stale:'+one['cacheKey'])
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as failure:
        module.conditions(**{**params,'at':at},claims={})
    assert failure.value.status_code==503

def test_unauthenticated_request(client):
    assert client.get('/api/v1/conditions?latitude=13&longitude=100&at=2026-10-17T18:00:00Z').status_code==401
