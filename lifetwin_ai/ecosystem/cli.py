"""Administrator commands. Doctor verification is an APPLICATION-LEVEL status only;
no external licence-verification service is called."""
import click
from flask.cli import with_appcontext

from models import db, User
from models_ecosystem import Doctor, VERIFY_VERIFIED, VERIFY_REJECTED, VERIFY_PENDING


def _find(email):
    u = User.query.filter_by(email=email.strip().lower()).first()
    return u.doctor_profile if u and u.role == "DOCTOR" else None


@click.command("doctor-list")
@with_appcontext
def doctor_list():
    """List all doctors and their verification status."""
    rows = Doctor.query.order_by(Doctor.id).all()
    if not rows:
        click.echo("No doctors registered.")
    for d in rows:
        click.echo(f"{d.doctor_code}  {d.verification_status:<9}  {d.user.email:<32}  "
                   f"Dr. {d.user.full_name} ({d.specialization}, {d.hospital})  licence={d.license_number}")


def _set(email, status):
    d = _find(email)
    if not d:
        raise click.ClickException(f"No doctor with email {email!r}.")
    d.verification_status = status
    db.session.commit()
    click.echo(f"{d.doctor_code} -> {status}")


@click.command("doctor-verify")
@click.argument("email")
@with_appcontext
def doctor_verify(email):
    """Mark a doctor VERIFIED (after you have checked their credentials yourself)."""
    _set(email, VERIFY_VERIFIED)


@click.command("doctor-reject")
@click.argument("email")
@with_appcontext
def doctor_reject(email):
    """Mark a doctor REJECTED (removes them from search and revokes data access)."""
    _set(email, VERIFY_REJECTED)


@click.command("doctor-pending")
@click.argument("email")
@with_appcontext
def doctor_pending(email):
    """Set a doctor back to PENDING."""
    _set(email, VERIFY_PENDING)


def register_cli(app):
    for cmd in (doctor_list, doctor_verify, doctor_reject, doctor_pending):
        app.cli.add_command(cmd)
