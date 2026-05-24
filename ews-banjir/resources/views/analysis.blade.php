@extends('layouts.app')

@section('content')
<h2 class="fw-bold mb-4">Analisis Dampak Banjir</h2>

<div class="row g-4">
    <div class="col-12">
        <div class="card p-5 text-white shadow-lg border-0 @if($impact['siaga_level'] == 1) bg-danger @elseif($impact['siaga_level'] == 2) bg-warning text-dark @else bg-success @endif">
            <h5 class="text-uppercase opacity-75 fw-bold">Prediksi Machine Learning:</h5>
            <h1 class="display-1 fw-bold mb-0">SIAGA {{ $impact['siaga_level'] }}</h1>
            <p class="fs-4">Kondisi: <strong>@if($impact['siaga_level'] == 1) KRITIS / EVAKUASI @else WASPADA @endif</strong></p>
        </div>
    </div>

    <div class="col-md-6">
        <div class="card p-4 h-100 shadow-sm border-start border-primary border-5">
            <h5 class="fw-bold text-primary mb-3"><i class="bi bi-map me-2"></i>Geografis & Penyebab</h5>
            <div class="alert alert-secondary py-3">
                <small class="d-block text-muted">Estimasi Luasan Terdampak:</small>
                <h3 class="fw-bold text-danger mb-0">{{ $impact['luas_terdampak'] }}</h3>
            </div>
            <h6 class="fw-bold mt-4">Analisis Akar Masalah:</h6>
            <p class="text-muted">{{ $impact['penyebab'] }}</p>
        </div>
    </div>

    <div class="col-md-6">
        <div class="card p-4 h-100 shadow-sm border-start border-success border-5">
            <h5 class="fw-bold text-success mb-4"><i class="bi bi-wallet2 me-2"></i>Estimasi Kerugian & Anggaran</h5>
            <div class="bg-light p-3 rounded mb-3 d-flex justify-content-between align-items-center">
                <span class="text-muted">Biaya Evakuasi Warga:</span>
                <h4 class="fw-bold text-dark mb-0">{{ $impact['biaya_evakuasi'] }}</h4>
            </div>
            <div class="bg-light p-3 rounded d-flex justify-content-between align-items-center">
                <span class="text-muted">Biaya Pemulihan Lingkungan:</span>
                <h4 class="fw-bold text-success mb-0">{{ $impact['biaya_pemulihan'] }}</h4>
            </div>
            <div class="mt-4 p-2 bg-info bg-opacity-10 rounded border border-info border-opacity-25 small">
                <i class="bi bi-info-circle me-1"></i> Perhitungan anggaran didasarkan pada data historis bencana wilayah setempat.
            </div>
        </div>
    </div>
</div>
@endsection