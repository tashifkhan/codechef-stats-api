"""Bounded durable refresh queue. A separate runner owns all expensive work.

Set REFRESH_WORKER_ENABLED only when a runner is scheduled. Public requests never
spawn detached tasks. Redis failures are explicit, not successful enqueue results.
"""
import argparse
import asyncio
import hashlib
import json
import os
import time
import uuid
from core.cache import command, get_json, set_json, redis_enabled

QUEUE = 'refresh:v1:due'
CAP = 1000
ENQUEUE = """
if redis.call('ZSCORE',KEYS[1],ARGV[1]) then return 1 end
if redis.call('ZCARD',KEYS[1]) >= tonumber(ARGV[3]) then return 0 end
redis.call('ZADD',KEYS[1],ARGV[2],ARGV[1])
return 1
"""
CLAIM = """
local jobs=redis.call('ZRANGEBYSCORE',KEYS[1],'-inf',ARGV[1],'LIMIT',0,1)
if #jobs==0 then return nil end
local lease=KEYS[2]..jobs[1]
if not redis.call('SET',lease,ARGV[2],'NX','EX',30) then
 redis.call('ZADD',KEYS[1],tonumber(ARGV[1])+30,jobs[1]) return nil end
redis.call('ZADD',KEYS[1],tonumber(ARGV[1])+30,jobs[1])
return jobs[1]
"""
FINISH = """
if redis.call('GET',KEYS[2])~=ARGV[1] then return 0 end
if ARGV[2]=='done' then redis.call('ZREM',KEYS[1],ARGV[3])
else redis.call('ZADD',KEYS[1],ARGV[4],ARGV[3]) end
redis.call('DEL',KEYS[2]) return 1
"""
CHECKPOINT = """
if redis.call('GET',KEYS[1])~=ARGV[1] then return 0 end
redis.call('SET',KEYS[2],ARGV[2],'EX',604800) return 1
"""

def enabled():
    return os.getenv('REFRESH_WORKER_ENABLED', '').lower() in {'1','true'} and redis_enabled()

def job_id(kind, subject):
    return hashlib.sha256((kind+':'+subject).encode()).hexdigest()

async def enqueue(kind, subject):
    if not enabled(): return False
    identifier = job_id(kind, subject)
    if not await set_json('refresh:v1:job:'+identifier, {'kind':kind,'subject':subject}, 604800): return False
    return bool(await command('eval', ENQUEUE, 1, QUEUE, identifier, time.time(), CAP))

class Job:
    def __init__(self, identifier, owner, payload, checkpoint):
        self.id, self.owner, self.payload = identifier, owner, payload
        self.data = checkpoint or {}
    async def save(self):
        result = await command('eval', CHECKPOINT, 2, 'refresh:v1:lease:'+self.id,
                               'refresh:v1:state:'+self.id, self.owner, json.dumps(self.data))
        if not result: raise RuntimeError('Refresh checkpoint could not be persisted')

async def run_once(handler):
    if not enabled(): raise RuntimeError('Refresh worker is disabled or Redis is unavailable')
    owner = uuid.uuid4().hex
    identifier = await command('eval', CLAIM, 2, QUEUE, 'refresh:v1:lease:', time.time(), owner)
    if not identifier: return False
    if isinstance(identifier, bytes): identifier = identifier.decode()
    payload = await get_json('refresh:v1:job:'+identifier)
    job = Job(identifier, owner, payload, await get_json('refresh:v1:state:'+identifier))
    done, delay = False, 2
    try:
        if not payload: done = True
        else:
            done = await asyncio.wait_for(handler(job), 20)
            job.data['attempts'] = 0
            await job.save()
    except Exception:
        job.data['attempts'] = min(int(job.data.get('attempts',0))+1, 12)
        delay = min(3600, 2 ** job.data['attempts'])
        await job.save()
    await command('eval', FINISH, 2, QUEUE, 'refresh:v1:lease:'+identifier,
                  owner, 'done' if done else 'retry', identifier, time.time()+delay)
    return True


RELEASE_LEASE = "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0"
# Seconds a public request may spend advancing its own refresh job.
INLINE_BUDGET = float(os.getenv('REFRESH_INLINE_BUDGET_SECONDS', '2.5'))

async def advance_inline(kind, subject, handler, budget):
    """Run refresh slices inside a request for at most `budget` seconds.

    Takes the same lease and checkpoint the runner uses, so a scheduled worker and
    concurrent requests never work one job at the same time. Progress is
    checkpointed per slice, so a slice cut off by the budget only loses itself.
    Returns True once the job has finished. Needs only Redis, not
    REFRESH_WORKER_ENABLED, so topics fill in without an external scheduler.
    """
    if budget < 0.25 or not redis_enabled():
        return False
    identifier = job_id(kind, subject)
    owner = uuid.uuid4().hex
    lease = 'refresh:v1:lease:' + identifier
    if not await command('set', lease, owner, ex=30, nx=True):
        return False
    done = False
    try:
        job = Job(identifier, owner, {'kind': kind, 'subject': subject},
                  await get_json('refresh:v1:state:' + identifier))
        # Back off after upstream refusals so throttled requests stay fast and
        # stop adding load to the platform.
        if float(job.data.get('retryAt', 0)) > time.time():
            return False
        deadline = time.monotonic() + budget
        try:
            while not done:
                left = deadline - time.monotonic()
                if left < 0.25:
                    break
                done = bool(await asyncio.wait_for(handler(job), left))
            if job.data.pop('attempts', None) is not None:
                job.data.pop('retryAt', None)
                await job.save()
        except asyncio.TimeoutError:
            # The budget cut a slice short. Completed slices are already saved.
            pass
        except Exception:
            attempts = min(int(job.data.get('attempts', 0)) + 1, 10)
            job.data['attempts'] = attempts
            job.data['retryAt'] = time.time() + min(3600, 5 * 2 ** (attempts - 1))
            await job.save()
    except Exception:
        done = False
    finally:
        await command('eval', RELEASE_LEASE, 1, lease, owner)
    return done

def main(handler, kind='topics'):
    parser = argparse.ArgumentParser(description='Run one bounded durable refresh slice. Schedule externally, no production schedule is enabled by this command.')
    parser.add_argument('--username', help='Enqueue a username before processing one slice')
    args = parser.parse_args()
    async def run():
        if args.username and not await enqueue(kind, args.username):
            raise RuntimeError('Refresh job was not queued')
        await run_once(handler)
    asyncio.run(run())
