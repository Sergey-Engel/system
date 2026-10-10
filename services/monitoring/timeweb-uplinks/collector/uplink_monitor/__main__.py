import argparse
from .exporter import make_server


def main():
    parser = argparse.ArgumentParser(description='Local candidate read-only exporter, not a live collector daemon.')
    parser.add_argument('action', choices=['serve'])
    parser.add_argument('--database', required=True)
    parser.add_argument('--port', type=int, default=19106)
    parser.add_argument('--health-file')
    parser.add_argument('--transport-state-file')
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    with make_server(args.database, args.port, health_path=args.health_file, pilot=args.pilot,
                     transport_state_path=args.transport_state_file) as server:
        print(f'Local candidate: http://127.0.0.1:{server.server_port}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
