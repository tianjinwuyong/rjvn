# -*- coding: utf-8 -*-
"""Append-only station history archives with verifiable hash chains."""
from __future__ import annotations
import hashlib,json,sqlite3,time,urllib.request,uuid
from pathlib import Path


class StationHistoryArchive:
    def __init__(self,db_path,station_code):
        self.db_path=Path(db_path);self.station_code=str(station_code).strip().lower();self.init_db()
    def connect(self):
        db=sqlite3.connect(str(self.db_path),timeout=30);db.row_factory=sqlite3.Row;db.execute("PRAGMA journal_mode=WAL");return db
    def init_db(self):
        with self.connect() as db:db.executescript("""
        CREATE TABLE IF NOT EXISTS history_archive_batches(
          archive_batch_id TEXT PRIMARY KEY,station_code TEXT NOT NULL,reason TEXT NOT NULL,
          previous_batch_hash TEXT NOT NULL DEFAULT '',record_count INTEGER NOT NULL,
          content_hash TEXT NOT NULL,sealed_at INTEGER NOT NULL,created_by TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS history_archive_records(
          archive_record_id TEXT PRIMARY KEY,archive_batch_id TEXT NOT NULL,source_table TEXT NOT NULL,
          source_key TEXT NOT NULL,source_payload TEXT NOT NULL,record_hash TEXT NOT NULL,
          archived_at INTEGER NOT NULL,UNIQUE(source_table,source_key),
          FOREIGN KEY(archive_batch_id) REFERENCES history_archive_batches(archive_batch_id));
        CREATE TABLE IF NOT EXISTS history_archive_outbox(
          event_id TEXT PRIMARY KEY,archive_batch_id TEXT NOT NULL,payload TEXT NOT NULL,
          created_at INTEGER NOT NULL,sent_at INTEGER,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '');
        CREATE TRIGGER IF NOT EXISTS archive_batches_no_update BEFORE UPDATE ON history_archive_batches BEGIN SELECT RAISE(ABORT,'sealed archive is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS archive_batches_no_delete BEFORE DELETE ON history_archive_batches BEGIN SELECT RAISE(ABORT,'sealed archive is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS archive_records_no_update BEFORE UPDATE ON history_archive_records BEGIN SELECT RAISE(ABORT,'archived record is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS archive_records_no_delete BEFORE DELETE ON history_archive_records BEGIN SELECT RAISE(ABORT,'archived record is immutable'); END;
        """)
    @staticmethod
    def _canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
    def seal_rows(self,table,rows,key_field,reason,created_by="SYSTEM"):
        reason=str(reason or "").strip();actor=str(created_by or "").strip()
        if not reason or not actor:raise ValueError("archive reason and created_by required")
        normalized=[]
        for item in rows or []:
            row=dict(item);key=str(row.get(key_field,""))
            if not key:raise ValueError(f"archive key {key_field} missing")
            payload=self._canonical(row);normalized.append((key,payload,hashlib.sha256(payload.encode()).hexdigest()))
        if not normalized:return None
        now=int(time.time()*1000);batch=str(uuid.uuid4())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous=db.execute("SELECT content_hash FROM history_archive_batches WHERE station_code=? ORDER BY sealed_at DESC LIMIT 1",(self.station_code,)).fetchone();prev=previous[0] if previous else ""
            fresh=[]
            for key,payload,digest in normalized:
                if not db.execute("SELECT 1 FROM history_archive_records WHERE source_table=? AND source_key=?",(table,key)).fetchone():fresh.append((key,payload,digest))
            if not fresh:return None
            content_hash=hashlib.sha256((prev+"".join(x[2] for x in fresh)).encode()).hexdigest()
            db.execute("INSERT INTO history_archive_batches VALUES(?,?,?,?,?,?,?,?)",(batch,self.station_code,reason,prev,len(fresh),content_hash,now,actor))
            for key,payload,digest in fresh:db.execute("INSERT INTO history_archive_records VALUES(?,?,?,?,?,?,?)",(str(uuid.uuid4()),batch,table,key,payload,digest,now))
            event=str(uuid.uuid4());manifest={"type":"STATION_HISTORY_ARCHIVE","stationCode":self.station_code,"payload":{"archiveBatchId":batch,"reason":reason,"previousBatchHash":prev,"recordCount":len(fresh),"contentHash":content_hash,"sealedAt":now,"createdBy":actor}}
            db.execute("INSERT INTO history_archive_outbox VALUES(?,?,?, ?,NULL,0,'')",(event,batch,self._canonical(manifest),now))
        return {"archive_batch_id":batch,"record_count":len(fresh),"content_hash":content_hash,"previous_batch_hash":prev}
    def verify(self):
        with self.connect() as db:
            batches=db.execute("SELECT * FROM history_archive_batches WHERE station_code=? ORDER BY sealed_at,archive_batch_id",(self.station_code,)).fetchall();previous=""
            for batch in batches:
                records=db.execute("SELECT source_payload,record_hash FROM history_archive_records WHERE archive_batch_id=? ORDER BY rowid",(batch["archive_batch_id"],)).fetchall()
                if batch["previous_batch_hash"]!=previous:return {"ok":False,"batch":batch["archive_batch_id"],"reason":"previous hash mismatch"}
                hashes=[]
                for row in records:
                    actual=hashlib.sha256(row["source_payload"].encode()).hexdigest()
                    if actual!=row["record_hash"]:return {"ok":False,"batch":batch["archive_batch_id"],"reason":"record hash mismatch"}
                    hashes.append(actual)
                actual=hashlib.sha256((previous+"".join(hashes)).encode()).hexdigest()
                if actual!=batch["content_hash"]:return {"ok":False,"batch":batch["archive_batch_id"],"reason":"batch hash mismatch"}
                previous=actual
        return {"ok":True,"batches":len(batches),"last_hash":previous}
    def snapshot(self,limit=500):
        with self.connect() as db:return {"batches":[dict(r) for r in db.execute("SELECT * FROM history_archive_batches ORDER BY sealed_at DESC LIMIT ?",(limit,))],"records":[dict(r) for r in db.execute("SELECT * FROM history_archive_records ORDER BY archived_at DESC LIMIT ?",(limit,))]}
    def sync_once(self,mes_url,limit=20):
        with self.connect() as db:rows=db.execute("SELECT * FROM history_archive_outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT ?",(limit,)).fetchall()
        sent=0
        for row in rows:
            try:
                req=urllib.request.Request(mes_url,data=row["payload"].encode(),headers={"Content-Type":"application/json"},method="POST")
                with urllib.request.urlopen(req,timeout=4) as response:response.read()
                with self.connect() as db:db.execute("UPDATE history_archive_outbox SET sent_at=?,attempts=attempts+1,last_error='' WHERE event_id=?",(int(time.time()*1000),row["event_id"]))
                sent+=1
            except Exception as exc:
                with self.connect() as db:db.execute("UPDATE history_archive_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?",(str(exc)[:300],row["event_id"]))
        return sent

