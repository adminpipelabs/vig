#!/usr/bin/expect -f
# Automated SSH key setup using expect

set HETZNER_IP "5.161.64.209"
set HETZNER_USER "root"
set SSH_KEY "$env(HOME)/.ssh/id_ed25519.pub"

puts "🔑 Automated SSH Key Setup"
puts "=========================="
puts ""
puts "Enter Hetzner root password:"
stty -echo
expect_user -re "(.*)\n"
set password $expect_out(1,string)
stty echo
puts ""

spawn ssh-copy-id -i $SSH_KEY ${HETZNER_USER}@${HETZNER_IP}
expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    "Permission denied" {
        puts "\n❌ Authentication failed. Check password."
        exit 1
    }
    eof
}

puts ""
puts "✅ SSH key copied!"
puts ""
puts "🧪 Testing passwordless connection..."

spawn ssh -o BatchMode=yes ${HETZNER_USER}@${HETZNER_IP} "echo '✅ Passwordless SSH works!'"
expect {
    eof {
        set result $expect_out(buffer)
        if {[string match "*✅*" $result]} {
            puts "🎉 SUCCESS! Passwordless SSH is now configured"
            puts ""
            puts "You can now run:"
            puts "  ssh ${HETZNER_USER}@${HETZNER_IP}"
            puts ""
            puts "Or use helper script:"
            puts "  cd /Users/mikaelo/vig && ./hetzner_commands.sh check-redeem"
        } else {
            puts "⚠️  Key copied but test failed. May need to check server config."
        }
    }
}
