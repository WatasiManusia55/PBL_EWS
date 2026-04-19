<?php
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\SensorController;

Route::get('/', [SensorController::class, 'index']);
Route::get('/analysis', [SensorController::class, 'analysis']);