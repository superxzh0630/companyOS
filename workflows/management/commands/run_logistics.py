"""
Management command to run the CompanyOS Logistics Engine.

This command runs a continuous loop that:
1. Pushes tickets from Sender Boxes to Big Hub (sender cycle)
2. Moves tickets from Big Hub to Department Receiver Boxes (grabber cycle)

The loop runs every 15 seconds until interrupted with Ctrl+C.

Usage:
    python manage.py run_logistics
"""
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from workflows.services import run_sender_cycle, run_grabber_cycle


class Command(BaseCommand):
    help = 'Run the CompanyOS Logistics Engine (15-second background cycles)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=15,
            help='Interval between cycles in seconds (default: 15)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run only one cycle and exit (useful for testing)'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['once']
        
        self.stdout.write(
            self.style.SUCCESS(
                "🚀 CompanyOS Logistics Engine Started... (Ctrl+C to stop)"
            )
        )
        self.stdout.write(f"   Cycle Interval: {interval} seconds")
        self.stdout.write("-" * 60)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                timestamp = timezone.now().strftime('%H:%M:%S')
                
                # Run sender cycle (SENDER_BOX -> BIG_HUB)
                sender_result = run_sender_cycle()
                
                # Run grabber cycle (BIG_HUB -> RECEIVER_BOX)
                grabber_result = run_grabber_cycle()
                
                # Log heartbeat
                sender_moved = sender_result.get('moved', 0)
                grabber_moved = grabber_result.get('total_moved', 0)
                
                status_msg = f"[{timestamp}] Heartbeat #{cycle_count}: "
                status_msg += f"Sender→Hub: {sender_moved} | Hub→Receivers: {grabber_moved}"
                
                if sender_moved > 0 or grabber_moved > 0:
                    self.stdout.write(self.style.SUCCESS(status_msg))
                else:
                    self.stdout.write(status_msg)
                
                # Verbose output for departments with activity
                if grabber_result.get('department_results'):
                    for dept_code, dept_result in grabber_result['department_results'].items():
                        if dept_result.get('moved', 0) > 0:
                            self.stdout.write(
                                f"   └── {dept_code}: {dept_result['message']}"
                            )
                
                # Exit if running in single-cycle mode
                if run_once:
                    self.stdout.write(self.style.SUCCESS("\n✅ Single cycle completed."))
                    break
                
                # Sleep until next cycle
                time.sleep(interval)
                
            except KeyboardInterrupt:
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("\n⏹️  Logistics Engine stopped by user."))
                self.stdout.write(f"   Total cycles completed: {cycle_count}")
                break
                
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"[{timezone.now().strftime('%H:%M:%S')}] Error: {e}")
                )
                # Shorter sleep on error before retry
                if not run_once:
                    time.sleep(5)
                else:
                    break
