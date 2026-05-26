import random

def get_risk_level(predicted_delay):
    if predicted_delay < 15:
        return "LOW"
    elif predicted_delay < 35:
        return "MEDIUM"
    elif predicted_delay < 65:
        return "HIGH"
    else:
        return "CRITICAL"

def generate_recommendations(predicted_delay, input_data, weather_severity, route_congestion):
    """
    Heuristics to recommend operational recovery actions:
    - Rerouting
    - Buffer adjustment
    - Passenger alerts
    """
    risk = get_risk_level(predicted_delay)
    recs = []
    
    # 1. Buffer Adjustment Recommendations
    if risk == "MEDIUM":
        recs.append({
            "type": "BUFFER_ADJUSTMENT",
            "action": "Extend gate turnaround window by +15 minutes",
            "impact": "Prevents secondary delay propagation to subsequent legs",
            "status": "SUGGESTED"
        })
    elif risk in ["HIGH", "CRITICAL"]:
        recs.append({
            "type": "BUFFER_ADJUSTMENT",
            "action": f"Apply +{int(min(predicted_delay * 0.8, 45))} minutes buffer padding to subsequent flight leg",
            "impact": "Protects downstream crew schedules and aircraft connections",
            "status": "APPROVED"
        })
        
    # 2. Rerouting / Operational Adjustments
    if float(input_data.get("previous_trip_delay", 0)) > 40:
        recs.append({
            "type": "AIRCRAFT_SWAP",
            "action": "Trigger reserve aircraft swap (Standby aircraft SFO-402)",
            "impact": "Reduces predicted departure delay by up to 25 minutes",
            "status": "CRITICAL"
        })
    
    if route_congestion > 25.0 and risk in ["HIGH", "CRITICAL"]:
        recs.append({
            "type": "REROUTING",
            "action": f"Reroute flight path via southern corridor (Fix KLAX_DEP_3)",
            "impact": f"Bypasses heavy congestion on standard {input_data['origin']}-{input_data['destination']} routing, saving ~12 mins",
            "status": "RECOMMENDED"
        })
    elif weather_severity > 6.0 and risk in ["HIGH", "CRITICAL"]:
        recs.append({
            "type": "REROUTING",
            "action": "Request low-altitude weather avoidance routing from ATC",
            "impact": "Bypasses active thunderstorm/convective cells, reducing holding risk",
            "status": "RECOMMENDED"
        })

    # 3. Passenger Alerts
    if risk == "MEDIUM":
        recs.append({
            "type": "PASSENGER_ALERT",
            "action": "Send departure gate standby SMS notification",
            "impact": "Ensures passengers are near the gate, enabling immediate boarding on clearance",
            "status": "QUEUED"
        })
    elif risk in ["HIGH", "CRITICAL"]:
        recs.append({
            "type": "PASSENGER_ALERT",
            "action": "Broadcast delay alert SMS & Push notification",
            "impact": "Keeps passengers informed, reduces customer support queues by 40%",
            "status": "DISPATCHED"
        })
        recs.append({
            "type": "PASSENGER_SERVICE",
            "action": "Issue $15 meal vouchers to passenger mobile wallets",
            "impact": "Mitigates customer dissatisfaction and meets regulatory compliance thresholds",
            "status": "AUTO-ISSUED"
        })
        
    if not recs:
        recs.append({
            "type": "MONITORING",
            "action": "Maintain normal schedule. Monitor live weather updates.",
            "impact": "No immediate actions required.",
            "status": "ACTIVE"
        })
        
    return recs

def generate_llm_explanation(predicted_delay, input_data, weather_severity, route_congestion):
    """
    Simulates an LLM (such as Gemini) generating explanation text.
    Constructs highly professional, detailed, and context-specific operational
    analyses and passenger messages using template heuristics that mimic natural reasoning.
    """
    origin = input_data["origin"]
    dest = input_data["destination"]
    weather_desc = []
    
    precip = float(input_data["precipitation"])
    vis = float(input_data["visibility"])
    wind = float(input_data["wind_speed"])
    prev_delay = float(input_data["previous_trip_delay"])
    
    if precip > 5.0:
        weather_desc.append(f"heavy precipitation ({precip:.1f} mm/h)")
    if vis < 3.0:
        weather_desc.append(f"severely reduced horizontal visibility ({vis:.1f} miles)")
    if wind > 25.0:
        weather_desc.append(f"strong turbulent winds ({wind:.1f} mph)")
        
    weather_str = ", coupled with ".join(weather_desc) if weather_desc else "stable weather conditions"
    
    # 1. Operations Explanation (Technical, diagnostic, analytical)
    ops_intro = (
        f"Diagnostic Analysis for Flight Path {origin} to {dest}.\n"
        f"Our machine learning pipeline (Ensemble RF + XGBoost) predicts a net delay risk of {predicted_delay:.1f} minutes. "
    )
    
    factors = []
    if prev_delay > 0:
        factors.append(f"1) Incoming aircraft delay propagation (+{prev_delay:.1f} mins) which impacts turnaround margins.")
    if weather_severity > 4.0:
        factors.append(f"2) Localized meteorological constraints: {weather_str} (Severity Index: {weather_severity:.1f}/10).")
    if route_congestion > 15.0:
        factors.append(f"3) Structural airway congestion score ({route_congestion:.1f} mins historical average delay) restricting departure slots.")
    if input_data.get("peak_hour_flag", 0) == 1:
        factors.append("4) Operation within airport peak-traffic slots, causing prolonged taxi-out queues.")
        
    if not factors:
        factors.append("1) Minor normal random operational noise; all systems are operating near peak efficiency.")
        
    ops_body = "Primary delay drivers identified in order of impact:\n" + "\n".join(factors)
    
    recs_summary = ""
    if predicted_delay >= 35:
        recs_summary = (
            "\n\nOperational Verdict: Critical threshold breached. Recommend aircraft swapping or alternate route assignment immediately. "
            "Downstream connection buffers have been adjusted dynamically by the decision engine to absorb the shock."
        )
    elif predicted_delay >= 15:
        recs_summary = (
            "\n\nOperational Verdict: Moderate delay expected. Adjust turnaround buffer and coordinate with gate personnel. "
            "Notify passengers to prevent bottlenecking at the gate."
        )
    else:
        recs_summary = "\n\nOperational Verdict: Operations normal. Keep monitoring current status."
        
    ops_explanation = ops_intro + "\n\n" + ops_body + recs_summary
    
    # 2. Passenger Explanation (Empathetic, clear, actionable)
    if predicted_delay < 15:
        pax_explanation = (
            f"Dear Passenger, we are pleased to inform you that your flight from {origin} to {dest} is operating on schedule. "
            f"We look forward to welcoming you on board. Please arrive at the gate by your scheduled boarding time."
        )
    else:
        pax_delay_est = int(predicted_delay)
        reason_pax = ""
        if weather_severity > 5.0:
            reason_pax = "severe weather conditions limiting airport visibility and runway capacity"
        elif prev_delay > 30:
            reason_pax = "the late arrival of your incoming aircraft from its previous flight leg"
        else:
            reason_pax = "air traffic control slot constraints and heavy route congestion"
            
        pax_explanation = (
            f"Dear Passenger, we want to let you know that your flight from {origin} to {dest} is currently experiencing a short delay. "
            f"We now estimate your departure will be delayed by approximately {pax_delay_est} minutes. This delay is due to {reason_pax}. "
            f"We sincerely apologize for this inconvenience. Your safety is our absolute priority, and our team is working diligently to make up time. "
            f"Please check flight information screens or your mobile boarding pass for updated gate details. "
        )
        if predicted_delay >= 35:
            pax_explanation += "A complimentary refreshment voucher has been sent to your digital wallet as a token of our appreciation for your patience."

    return {
        "operations_report": ops_explanation,
        "passenger_notification": pax_explanation
    }
