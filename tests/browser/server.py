"""Local browser fixture service with newly constructed source responses."""
import json
import os
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


def employee(number):
    return {'ID': number, 'NAME': f'Testperson {number - 100:03}', 'EMPSTART': '2025-01-01',
            'EMPEND': '2027-12-31', 'HRSDAY': 8, 'HRSWEEK': 40, 'WORKDAYS': '1111100'}


people = [employee(n) for n in (101, 102, 103)]
groups = [{'ID': 1, 'NAME': 'Team A', 'SUPERID': 0},
          {'ID': 2, 'NAME': 'Team B', 'SUPERID': 1},
          {'ID': 3, 'NAME': 'Team C', 'SUPERID': 1}]
responses = {
    '/api/dev/mode': {'dev_mode': True},
    '/api/auth/me': {'showabs_mode': 0},
    '/api/groups': groups,
    '/api/groups/1/members': [],
    '/api/groups/2/members': [people[0], people[2]],
    '/api/groups/3/members': [people[1], people[2]],
    '/api/employees': people,
    '/api/shifts': [{'ID': sid, 'NAME': name,
                     **{f'STARTEND{i}': '08:00-16:00' for i in range(8)},
                     **{f'DURATION{i}': 8 for i in range(8)}} for sid, name in [(201, 'Dienst A'), (202, 'Dienst B'), (203, 'Dienst C')]],
    '/api/workplaces': [{'ID': 301, 'NAME': 'Arbeitsplatz 1'}, {'ID': 302, 'NAME': 'Arbeitsplatz 2'}],
    '/api/holidays': [],
    '/api/staffing-requirements': {'shift_requirements': [
        {'id': 400 + gid * 10 + sid, 'group_id': gid, 'weekday': 0, 'shift_id': sid,
         'workplace_id': 301, 'min': 1, 'max': 2} for gid in (2, 3) for sid in (201, 202)], 'daily_requirements': []},
    '/api/staffing-requirements/special': [],
    '/api/restrictions': [],
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        request = urlsplit(self.path)
        if request.path != '/api/dev/mode' and self.headers.get('Authorization') != 'Bearer __dev_mode__':
            self.send_error(401)
            return
        if request.path == '/api/schedule':
            params = parse_qs(request.query)
            group = int(params['group_id'][0])
            rows = []
            if params['year'] == ['2026'] and params['month'] == ['1']:
                for person in responses.get(f'/api/groups/{group}/members', []):
                    rows.append({'employee_id': person['ID'], 'date': str(date(2026, 1, 12)),
                                 'kind': 'shift', 'shift_id': 201, 'workplace_id': 302})
            data = rows
        else:
            if request.path not in responses:
                self.send_error(404)
                return
            data = responses[request.path]
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


if __name__ == '__main__':
    from sp5generator.webapp import create_app
    import uvicorn
    source = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=source.serve_forever, daemon=True).start()
    os.environ['SP5_API_URL'] = f'http://127.0.0.1:{source.server_port}'
    os.environ['SP5_API_DEV_MODE'] = 'true'
    uvicorn.run(create_app(os.environ['WEB_TEST_STATE']), host='127.0.0.1',
                port=int(os.environ.get('WEB_TEST_PORT', '8765')), access_log=False)
