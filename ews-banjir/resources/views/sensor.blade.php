@extends('layouts.app')

@section('content')
<div class="vh-100 d-flex flex-column" style="margin-top:-1.5rem;">

    {{-- HEADER --}}
    <div class="d-flex justify-content-between align-items-center mb-3 pt-3">
        <div>
            <h2 class="fw-bold text-dark mb-0">Monitoring Node Deteksi EWS</h2>
            <small class="text-muted">Backend: Laravel REST API | Maps: Leaflet.js | CCTV Live Stream</small>
        </div>

        <span class="badge bg-white text-dark border p-3 shadow-sm rounded-pill">
            <i class="bi bi-clock-fill text-primary me-2"></i>
            <span id="realtime-clock" class="fw-bold fs-5">--:--:--</span>
        </span>
    </div>

    {{-- SENSOR CARD --}}
    <div class="row g-2 mb-3">

        <div class="col">
            <div class="card sensor-card border-bottom border-primary border-5 h-100 shadow">
                <div class="card-body py-3 text-center">
                    <small class="label-sensor text-muted fw-bold text-uppercase">A01 Ultrasonic</small>
                    <h4 class="fw-bold mb-0 text-primary" id="val-water">-- cm</h4>
                </div>
            </div>
        </div>

        <div class="col">
            <div class="card sensor-card border-bottom border-info border-5 h-100 shadow">
                <div class="card-body py-3 text-center">
                    <small class="label-sensor text-muted fw-bold text-uppercase">Rainfall Bucket</small>
                    <h4 class="fw-bold mb-0 text-info" id="val-rain">-- mm</h4>
                </div>
            </div>
        </div>

        <div class="col">
            <div class="card sensor-card border-bottom border-success border-5 h-100 shadow">
                <div class="card-body py-3 text-center">
                    <small class="label-sensor text-muted fw-bold text-uppercase">Flow SEN-0187</small>
                    <h4 class="fw-bold mb-0 text-success" id="val-flow">-- L/m</h4>
                </div>
            </div>
        </div>

        <div class="col">
            <div class="card sensor-card border-bottom border-warning border-5 h-100 shadow">
                <div class="card-body py-3 text-center">
                    <small class="label-sensor text-muted fw-bold text-uppercase">GY-BME280</small>
                    <h4 class="fw-bold mb-0 text-warning" id="val-env">--°C / --%</h4>
                </div>
            </div>
        </div>

        <div class="col">
            <div id="float-card" class="card sensor-card border-bottom border-secondary border-5 h-100 shadow">
                <div class="card-body py-3 text-center">
                    <small class="label-sensor text-muted fw-bold text-uppercase">Float SEN-0105</small>
                    <h4 class="fw-bold mb-0" id="val-float">NORMAL</h4>
                </div>
            </div>
        </div>

    </div>

    {{-- MAIN CONTENT --}}
    <div class="row g-3 flex-grow-1 mb-3" style="min-height:0;">

        {{-- CHART --}}
        <div class="col-md-6 h-100">
            <div class="card p-3 h-100 shadow-sm border-0 d-flex flex-column">
                <h6 class="fw-bold mb-2 border-bottom pb-1">
                    <i class="bi bi-graph-up me-2"></i>Real-time Chart
                </h6>

                <div class="flex-grow-1 position-relative">
                    <canvas id="waterChart"></canvas>
                </div>
            </div>
        </div>

        {{-- MAP --}}
        <div class="col-md-3 h-100">
            <div class="card p-3 h-100 shadow-sm border-0 d-flex flex-column">
                <h6 class="fw-bold mb-2 border-bottom pb-1">
                    <i class="bi bi-geo-alt me-2"></i>Lokasi Node
                </h6>

                <div id="map" class="flex-grow-1 rounded"></div>
            </div>
        </div>

        {{-- CCTV --}}
        <div class="col-md-3 h-100">
            <div class="card bg-dark text-white p-3 h-100 d-flex flex-column shadow-lg border-0">

                <div class="d-flex justify-content-between mb-2">
                    <span class="small fw-bold">IP CCTV</span>
                    <span class="badge bg-danger live-badge">LIVE</span>
                </div>

                <div class="flex-grow-1 rounded overflow-hidden bg-black position-relative">

                    <video
                        id="cctvPlayer"
                        autoplay
                        muted
                        controls
                        playsinline
                        style="width:100%; height:100%; object-fit:cover;">
                    </video>

                    <div id="cctvLoading"
                        class="position-absolute top-50 start-50 translate-middle text-center text-white">
                        <div class="spinner-border spinner-border-sm mb-2"></div>
                        <div style="font-size:11px;">Connecting CCTV (HLS)...</div>
                    </div>

                </div>

            </div>
        </div>

    </div>
</div>

{{-- CSS --}}
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

<style>
main{
    height:100vh;
    overflow:hidden !important;
}

.sensor-card{
    border-radius:15px !important;
}

.label-sensor{
    font-size:0.7rem !important;
    display:block;
}

#map{
    background:#eee;
}

.live-badge{
    font-size:8px;
    animation:blink 1s infinite;
}

@keyframes blink{
    0%{opacity:1;}
    50%{opacity:0;}
    100%{opacity:1;}
}
</style>
@endsection


@section('scripts')

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>

<script>
document.addEventListener("DOMContentLoaded", function () {

    /* CLOCK */
    setInterval(() => {
        document.getElementById('realtime-clock').innerText =
            new Date().toLocaleTimeString('id-ID');
    }, 1000);

    /* MAP */
    const map = L.map('map').setView([-6.362, 106.827], 15);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:'© OpenStreetMap'
    }).addTo(map);

    L.marker([-6.362, 106.827])
        .addTo(map)
        .bindPopup('<b>Node Deteksi EWS</b><br>Lokasi: Pintu Air RT 01')
        .openPopup();

    /* CHART */
    const ctx = document.getElementById('waterChart').getContext('2d');

    const waterChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Water Level',
                data: [],
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13,110,253,0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive:true,
            maintainAspectRatio:false,
            plugins:{ legend:{ display:false } },
            scales:{
                x:{ display:false },
                y:{ min:140, max:220 }
            }
        }
    });

    /* SENSOR SIMULATION */
    setInterval(() => {

        const level = (Math.random() * (190 - 160) + 160).toFixed(1);

        document.getElementById('val-water').innerText = level + ' cm';
        document.getElementById('val-rain').innerText =
            (Math.random() * 10).toFixed(1) + ' mm';

        document.getElementById('val-flow').innerText =
            (Math.random() * 20 + 5).toFixed(1) + ' L/m';

        document.getElementById('val-env').innerText = '29°C / 80%';

        if (waterChart.data.labels.length > 20) {
            waterChart.data.labels.shift();
            waterChart.data.datasets[0].data.shift();
        }

        waterChart.data.labels.push('');
        waterChart.data.datasets[0].data.push(level);
        waterChart.update('none');

    }, 2000);

    /* =========================
       CCTV HLS ONLY STREAM
    ========================== */

    const video = document.getElementById("cctvPlayer");
    const loading = document.getElementById("cctvLoading");

    const streamUrl = "http://192.168.10.250:8888/cam1/index.m3u8";

    if (!streamUrl.includes(".m3u8")) {
        loading.innerHTML = "ERROR: HLS (.m3u8) required";
    } else {

        if (Hls.isSupported()) {

            const hls = new Hls({
                lowLatencyMode: true,
                liveSyncDurationCount: 2
            });

            hls.loadSource(streamUrl);
            hls.attachMedia(video);

            hls.on(Hls.Events.MANIFEST_PARSED, function () {
                loading.style.display = "none";
                video.play().catch(()=>{});
            });

            hls.on(Hls.Events.ERROR, function (event, data) {
                console.error("HLS Error:", data);

                if (data.fatal) {
                    switch (data.type) {
                        case Hls.ErrorTypes.NETWORK_ERROR:
                            hls.startLoad();
                            break;
                        case Hls.ErrorTypes.MEDIA_ERROR:
                            hls.recoverMediaError();
                            break;
                        default:
                            hls.destroy();
                            break;
                    }
                }
            });

        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {

            video.src = streamUrl;

            video.addEventListener('loadedmetadata', function () {
                loading.style.display = "none";
                video.play();
            });

        } else {
            loading.innerHTML = "Browser tidak support HLS (.m3u8)";
        }
    }

});
</script>

@endsection