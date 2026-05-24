<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flood Monitoring</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        body { background-color: #f4f7f6; font-family: 'Inter', sans-serif; }
        .sidebar { min-height: 100vh; background: #1a1d20; color: white; padding-top: 20px; position: fixed; width: 16.66667%; }
        .nav-link { color: rgba(255,255,255,0.6); border-radius: 10px; margin: 5px 15px; transition: 0.3s; }
        .nav-link.active { background: #0d6efd; color: white; box-shadow: 0 4px 10px rgba(13,110,253,0.3); }
        .nav-link:hover { color: white; background: rgba(255,255,255,0.1); }
        main { margin-left: 16.66667%; padding: 2rem; }
        .card { border: none; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); transition: 0.3s; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <nav class="col-md-2 d-none d-md-block sidebar px-0">
                <div class="text-center mb-4 px-3">
                    <h4 class="fw-bold text-primary mb-0">EWS</h4>
                    <small class="text-muted">Kelompok 3 TMJ PNJ</small>
                </div>
                <ul class="nav flex-column">
                    <li class="nav-item">
                        <a class="nav-link {{ request()->is('/') ? 'active' : '' }}" href="/">
                            <i class="bi bi-droplet-fill me-2"></i> Real-time Sensor
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {{ request()->is('analysis') ? 'active' : '' }}" href="/analysis">
                            <i class="bi bi-cpu-fill me-2"></i> Analisis Dampak
                        </a>
                    </li>
                </ul>
            </nav>
            <main class="col-md-10">
                @yield('content')
            </main>
        </div>
    </div>
    @yield('scripts')
</body>
</html>