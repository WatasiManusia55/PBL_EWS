<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class SensorController extends Controller
{
    // Halaman 1: Monitoring Semua Sensor
    public function index() {
        $data = [
            'water_level' => 165.2, // A01 Ultrasonic [cite: 27]
            'flow_rate'   => 12.4,  // SEN-0187 [cite: 28]
            'rainfall'    => 5.2,   // Tipping Bucket [cite: 24]
            'temp'        => 28.5,  // GY-BME280 [cite: 25]
            'humidity'    => 82,    // GY-BME280 [cite: 25]
            'pressure'    => 1011,  // GY-BME280 [cite: 25]
            'float'       => 'Safe',// Water Float Sensor [cite: 26]
            'last_update' => now()->format('H:i:s')
        ];
        return view('sensor', compact('data'));
    }

    // Halaman 2: 4 Fitur Analisis ML (Dampak, Biaya, Penyebab) 
    public function analysis() {
        $impact = [
            'siaga_level' => 2, // 1. Kondisi Siaga (1-4)
            'luas_terdampak' => '2.1 km²', // 2. Luasan Daerah
            'biaya_evakuasi' => 'Rp 18.500.000', // 3. Anggaran Evakuasi
            'biaya_pemulihan' => 'Rp 35.000.000', // 3. Anggaran Pemulihan
            'penyebab' => 'Akumulasi curah hujan tinggi di hulu sungai dan penyumbatan drainase lokal.' // 4. Penyebab
        ];
        return view('analysis', compact('impact'));
    }
}